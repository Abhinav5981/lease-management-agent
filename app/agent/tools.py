"""
app/agent/tools.py
-------------------
LangGraph tools for the FastAPI-integrated Lease Manager Agent.

All tools are created via build_tools(session, qdrant) — a factory that binds
each tool to the per-request SQLAlchemy session and the Qdrant singleton.
This gives every HTTP request its own DB session while keeping the graph
stateless at the module level.

Tool design rules
──────────────────
• Every tool is async.
• Every tool returns a JSON string (never raises).
• Errors are returned as {"error": "..."} so the LLM can reason about
  failures and suggest corrective action rather than crashing the ReAct loop.
• Pydantic input schemas auto-generate the JSON schema the LLM sees.
• Mutations call session.commit(); on exception they call session.rollback().
"""

import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.unit_repository import UnitRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.lease_repository import LeaseRepository
from app.services.lease_service import LeaseService
from app.services.maintenance_service import MaintenanceService
from app.services.renewal_service import RenewalService
from app.vector.qdrant_client import QdrantService
from app.rag.retriever import RAGRetriever


# ══════════════════════════════════════════════════════════════════════════
# INPUT SCHEMAS
# ══════════════════════════════════════════════════════════════════════════

class SearchPropertiesInput(BaseModel):
    location: Optional[str] = Field(
        None,
        description="Dubai area name, e.g. 'Dubai Marina', 'Downtown Dubai', 'Business Bay', 'JVC', 'Palm Jumeirah'.",
    )
    unit_type: Optional[str] = Field(
        None,
        description="Unit type: studio | 1br | 2br | 3br | 4br | penthouse | commercial | retail.",
    )
    bedrooms: Optional[int] = Field(
        None,
        description="Number of bedrooms. Use 0 for studio.",
    )
    max_rent_aed: Optional[float] = Field(
        None,
        description="Maximum annual rent in AED.",
    )


class SearchTenantInput(BaseModel):
    query: str = Field(
        description="Search term: full or partial name, email address, phone number, or Emirates ID.",
    )


class CreateLeaseInput(BaseModel):
    unit_id: str = Field(description="UUID of the available unit to lease.")
    tenant_id: str = Field(description="UUID of the tenant signing the lease.")
    start_date: str = Field(description="Lease start date in YYYY-MM-DD format.")
    end_date: str = Field(description="Lease end date in YYYY-MM-DD format.")
    annual_rent_aed: float = Field(
        description="Agreed annual rent in AED. Stored for RERA compliance — not a payment instruction.",
        gt=0,
    )
    notice_period_days: int = Field(
        default=60,
        description="Notice period in days required to vacate (default 60).",
        ge=1,
    )


class RenewLeaseInput(BaseModel):
    lease_id: str = Field(description="UUID of the active lease to renew.")
    new_end_date: str = Field(description="Proposed new lease end date in YYYY-MM-DD format.")
    proposed_rent_aed: float = Field(
        description="Proposed annual rent for the renewed term in AED.",
        gt=0,
    )


class CreateMaintenanceInput(BaseModel):
    unit_id: str = Field(description="UUID of the unit with the issue.")
    tenant_id: str = Field(description="UUID of the tenant raising the request.")
    category: str = Field(
        description=(
            "Issue category: hvac | plumbing | electrical | carpentry | "
            "painting | appliances | pest_control | cleaning | general."
        ),
    )
    priority: str = Field(
        description="Priority level: emergency | high | medium | low.",
    )
    title: str = Field(description="Short descriptive title (max 255 characters).")
    description: Optional[str] = Field(None, description="Detailed description of the issue.")


class ViewLeaseInput(BaseModel):
    lease_ref: str = Field(
        description="Lease UUID or human-readable lease number, e.g. LSE-2026-001042.",
    )


class ViewExpiringLeasesInput(BaseModel):
    days_ahead: int = Field(
        default=90,
        description="Number of days from today to look ahead for expiring leases (default 90).",
        ge=1,
        le=365,
    )


class KnowledgeSearchInput(BaseModel):
    query: str = Field(
        description=(
            "Natural language question about RERA regulations, company policies, "
            "lease terms, or tenant FAQs."
        ),
    )
    source: Optional[str] = Field(
        None,
        description=(
            "Restrict search to a specific knowledge source: "
            "lease_policies | tenant_faq | move_in_guidelines | move_out_guidelines | renewal_policies."
        ),
    )
    doc_type: Optional[str] = Field(
        None,
        description="Filter by document type: policy | faq | guideline.",
    )


# ══════════════════════════════════════════════════════════════════════════
# TOOL FACTORY
# ══════════════════════════════════════════════════════════════════════════

def build_tools(session: AsyncSession, qdrant: QdrantService) -> list:
    """
    Create the full tool list bound to the given DB session and Qdrant service.
    Called once per agent invocation so each HTTP request gets its own session.
    """

    # ── TOOL 1: search_properties ─────────────────────────────────────────

    @tool("search_properties", args_schema=SearchPropertiesInput)
    async def search_properties(
        location: Optional[str] = None,
        unit_type: Optional[str] = None,
        bedrooms: Optional[int] = None,
        max_rent_aed: Optional[float] = None,
    ) -> str:
        """
        Search for available units in the portfolio.
        Filter by Dubai area, unit type, number of bedrooms, or maximum annual rent.
        Returns up to 20 matching units with building name and location.
        """
        try:
            from app.models.unit import UnitType
            from app.models.building import Building
            from sqlalchemy import select
            from app.models.unit import Unit, UnitStatus

            repo = UnitRepository(session)

            ut = UnitType(unit_type) if unit_type else None
            units = await repo.search_available(
                area=location,
                unit_type=ut,
                bedrooms=bedrooms,
            )

            # Apply rent filter in Python (avoids adding it to the repo for MVP)
            if max_rent_aed is not None:
                units = [u for u in units if u.annual_rent_aed is None or float(u.annual_rent_aed) <= max_rent_aed]

            if not units:
                return json.dumps({
                    "units": [],
                    "message": "No available units match the search criteria.",
                })

            results = [
                {
                    "id": str(u.id),
                    "unit_number": u.unit_number,
                    "floor": u.floor_number,
                    "type": u.unit_type.value,
                    "bedrooms": u.bedrooms,
                    "bathrooms": u.bathrooms,
                    "area_sqft": float(u.area_sqft) if u.area_sqft else None,
                    "building": u.building.name if u.building else None,
                    "location": u.building.area if u.building else None,
                    "status": u.status.value,
                }
                for u in units
            ]
            return json.dumps({"units": results, "count": len(results)})

        except Exception as exc:
            return json.dumps({"error": f"search_properties failed: {exc}"})

    # ── TOOL 2: search_tenant ─────────────────────────────────────────────

    @tool("search_tenant", args_schema=SearchTenantInput)
    async def search_tenant(query: str) -> str:
        """
        Search for tenants by full or partial name, email address,
        phone number, or Emirates ID.
        Returns matching tenant profiles including KYC document expiry dates
        and blacklist status.
        """
        try:
            repo = TenantRepository(session)
            tenants = await repo.search(query)

            if not tenants:
                return json.dumps({
                    "tenants": [],
                    "message": "No tenants found matching that query.",
                })

            results = [
                {
                    "id": str(t.id),
                    "name": f"{t.first_name} {t.last_name}",
                    "email": t.email,
                    "phone": t.phone,
                    "nationality": t.nationality,
                    "emirates_id": t.emirates_id,
                    "passport_expiry": t.passport_expiry.isoformat() if t.passport_expiry else None,
                    "emirates_id_expiry": t.emirates_id_expiry.isoformat() if t.emirates_id_expiry else None,
                    "visa_expiry": t.visa_expiry.isoformat() if t.visa_expiry else None,
                    "is_blacklisted": t.is_blacklisted,
                }
                for t in tenants
            ]
            return json.dumps({"tenants": results, "count": len(results)})

        except Exception as exc:
            return json.dumps({"error": f"search_tenant failed: {exc}"})

    # ── TOOL 3: create_lease ──────────────────────────────────────────────

    @tool("create_lease", args_schema=CreateLeaseInput)
    async def create_lease(
        unit_id: str,
        tenant_id: str,
        start_date: str,
        end_date: str,
        annual_rent_aed: float,
        notice_period_days: int = 60,
    ) -> str:
        """
        Create a new tenancy agreement in DRAFT status.
        Validates that the unit is available and the tenant is not blacklisted.
        The unit is marked as 'reserved' immediately so no duplicate lease can be created.
        The lease becomes ACTIVE only after digital signing by both parties and Ejari registration.
        IMPORTANT: Always confirm unit, tenant, dates, and rent with the user before calling this tool.
        """
        try:
            from app.schemas.lease import LeaseCreate

            svc = LeaseService(session)
            lease = await svc.create_lease(
                LeaseCreate(
                    unit_id=uuid.UUID(unit_id),
                    tenant_id=uuid.UUID(tenant_id),
                    start_date=date.fromisoformat(start_date),
                    end_date=date.fromisoformat(end_date),
                    annual_rent_aed=Decimal(str(annual_rent_aed)),
                    notice_period_days=notice_period_days,
                )
            )
            await session.commit()

            return json.dumps({
                "success": True,
                "lease": {
                    "id": str(lease.id),
                    "lease_number": lease.lease_number,
                    "status": lease.status.value,
                    "start_date": lease.start_date.isoformat(),
                    "end_date": lease.end_date.isoformat(),
                    "annual_rent_aed": float(lease.annual_rent_aed),
                    "notice_period_days": lease.notice_period_days,
                },
                "next_steps": [
                    "Send the tenancy contract to both parties for digital signing.",
                    "Register with Ejari within 30 days of signing.",
                    "Update lease status to ACTIVE after Ejari registration.",
                ],
            })

        except Exception as exc:
            await session.rollback()
            return json.dumps({"error": f"create_lease failed: {exc}"})

    # ── TOOL 4: view_lease ────────────────────────────────────────────────

    @tool("view_lease", args_schema=ViewLeaseInput)
    async def view_lease(lease_ref: str) -> str:
        """
        Retrieve full details of a lease by UUID or lease number (e.g. LSE-2026-001042).
        Returns lease terms, status, tenant profile, unit details, Ejari registration,
        and signing timestamps.
        """
        try:
            repo = LeaseRepository(session)
            lease = None

            # Try UUID first, fall back to lease number
            try:
                lease = await repo.get_with_details(uuid.UUID(lease_ref))
            except ValueError:
                lease = await repo.get_by_lease_number(lease_ref)

            if not lease:
                return json.dumps({"error": f"No lease found for reference '{lease_ref}'."})

            return json.dumps({
                "lease": {
                    "id": str(lease.id),
                    "lease_number": lease.lease_number,
                    "status": lease.status.value,
                    "start_date": lease.start_date.isoformat(),
                    "end_date": lease.end_date.isoformat(),
                    "annual_rent_aed": float(lease.annual_rent_aed),
                    "notice_period_days": lease.notice_period_days,
                    "ejari_number": lease.ejari_number,
                    "ejari_registration_date": (
                        lease.ejari_registration_date.isoformat()
                        if lease.ejari_registration_date else None
                    ),
                    "signed_by_tenant_at": (
                        lease.signed_by_tenant_at.isoformat()
                        if lease.signed_by_tenant_at else None
                    ),
                    "signed_by_company_at": (
                        lease.signed_by_company_at.isoformat()
                        if lease.signed_by_company_at else None
                    ),
                    "tenant": {
                        "id": str(lease.tenant.id),
                        "name": f"{lease.tenant.first_name} {lease.tenant.last_name}",
                        "email": lease.tenant.email,
                        "phone": lease.tenant.phone,
                        "emirates_id": lease.tenant.emirates_id,
                        "visa_expiry": (
                            lease.tenant.visa_expiry.isoformat()
                            if lease.tenant.visa_expiry else None
                        ),
                    } if lease.tenant else None,
                    "unit": {
                        "id": str(lease.unit.id),
                        "unit_number": lease.unit.unit_number,
                        "type": lease.unit.unit_type.value,
                        "floor": lease.unit.floor_number,
                        "building": lease.unit.building.name if lease.unit.building else None,
                        "location": lease.unit.building.area if lease.unit.building else None,
                    } if lease.unit else None,
                }
            })

        except Exception as exc:
            return json.dumps({"error": f"view_lease failed: {exc}"})

    # ── TOOL 5: renew_lease ───────────────────────────────────────────────

    @tool("renew_lease", args_schema=RenewLeaseInput)
    async def renew_lease(
        lease_id: str,
        new_end_date: str,
        proposed_rent_aed: float,
    ) -> str:
        """
        Initiate a RERA-compliant renewal offer for an active lease.
        Automatically computes the 90-day notice deadline and flags whether
        the offer is within RERA Law 33 compliance.
        Creates a Renewal record in 'offered' status awaiting tenant response.
        Only one open renewal is allowed per lease at a time.
        """
        try:
            from app.schemas.renewal import RenewalCreate

            svc = RenewalService(session)
            renewal = await svc.initiate_renewal(
                RenewalCreate(
                    lease_id=uuid.UUID(lease_id),
                    new_end_date=date.fromisoformat(new_end_date),
                    proposed_rent_aed=Decimal(str(proposed_rent_aed)),
                )
            )
            await session.commit()

            compliance_note = (
                "Renewal is within the RERA 90-day notice window."
                if renewal.rera_notice_compliant
                else (
                    f"WARNING: RERA 90-day notice deadline was {renewal.notice_due_by.isoformat()}. "
                    "This offer may be non-compliant with RERA Law 33 — advise the tenant of their rights."
                )
            )

            return json.dumps({
                "success": True,
                "renewal": {
                    "id": str(renewal.id),
                    "status": renewal.status.value,
                    "new_start_date": renewal.new_start_date.isoformat(),
                    "new_end_date": renewal.new_end_date.isoformat(),
                    "previous_rent_aed": float(renewal.previous_rent_aed),
                    "proposed_rent_aed": float(renewal.proposed_rent_aed),
                    "notice_due_by": renewal.notice_due_by.isoformat(),
                    "rera_notice_compliant": renewal.rera_notice_compliant,
                },
                "compliance_note": compliance_note,
                "next_steps": [
                    "Send the renewal offer to the tenant in writing (email or registered mail).",
                    "Tenant has 15 days to respond per company policy.",
                    "If accepted, issue a new Ejari certificate for the renewed term.",
                ],
            })

        except Exception as exc:
            await session.rollback()
            return json.dumps({"error": f"renew_lease failed: {exc}"})

    # ── TOOL 6: create_maintenance_request ───────────────────────────────

    @tool("create_maintenance_request", args_schema=CreateMaintenanceInput)
    async def create_maintenance_request(
        unit_id: str,
        tenant_id: str,
        category: str,
        priority: str,
        title: str,
        description: Optional[str] = None,
    ) -> str:
        """
        Log a new maintenance or repair request for a unit.
        Automatically calculates the SLA due timestamp from the priority:
          emergency → 1 hour  |  high → 6 hours
          medium    → 48 hours |  low  → 120 hours (5 business days)
        Links the request to the tenant's active lease if one exists.
        """
        try:
            from app.models.maintenance import MaintenanceCategory, MaintenancePriority
            from app.schemas.maintenance import MaintenanceRequestCreate

            svc = MaintenanceService(session)
            req = await svc.create_request(
                MaintenanceRequestCreate(
                    unit_id=uuid.UUID(unit_id),
                    tenant_id=uuid.UUID(tenant_id),
                    category=MaintenanceCategory(category),
                    priority=MaintenancePriority(priority),
                    title=title,
                    description=description,
                )
            )
            await session.commit()

            sla_map = {"emergency": 1, "high": 6, "medium": 48, "low": 120}
            sla_hours = sla_map.get(priority, 48)

            return json.dumps({
                "success": True,
                "maintenance_request": {
                    "id": str(req.id),
                    "reference_number": req.reference_number,
                    "status": req.status.value,
                    "category": req.category.value,
                    "priority": req.priority.value,
                    "title": req.title,
                    "sla_due_at": req.sla_due_at.isoformat() if req.sla_due_at else None,
                    "reported_at": req.reported_at.isoformat(),
                },
                "sla_hours": sla_hours,
                "message": (
                    f"Request {req.reference_number} logged. "
                    f"SLA: respond within {sla_hours} hour(s)."
                ),
            })

        except Exception as exc:
            await session.rollback()
            return json.dumps({"error": f"create_maintenance_request failed: {exc}"})

    # ── TOOL 7: view_expiring_leases ──────────────────────────────────────

    @tool("view_expiring_leases", args_schema=ViewExpiringLeasesInput)
    async def view_expiring_leases(days_ahead: int = 90) -> str:
        """
        List all active leases expiring within the next N days (default 90).
        Results are ordered by expiry date ascending so the most urgent leases
        appear first. Use this to identify the renewal pipeline and check
        RERA 90-day notice compliance.
        """
        try:
            from datetime import date as _date, timedelta

            repo = LeaseRepository(session)
            leases = await repo.get_expiring_soon(days_ahead)

            if not leases:
                return json.dumps({
                    "leases": [],
                    "message": f"No active leases expiring in the next {days_ahead} days.",
                })

            today = _date.today()
            results = []
            for lease in leases:
                days_remaining = (lease.end_date - today).days
                notice_due_by = lease.end_date - timedelta(days=90)
                notice_compliant = today <= notice_due_by

                results.append({
                    "id": str(lease.id),
                    "lease_number": lease.lease_number,
                    "end_date": lease.end_date.isoformat(),
                    "days_remaining": days_remaining,
                    "annual_rent_aed": float(lease.annual_rent_aed),
                    "rera_90day_notice_due_by": notice_due_by.isoformat(),
                    "rera_notice_window_open": notice_compliant,
                    "tenant": {
                        "id": str(lease.tenant.id),
                        "name": f"{lease.tenant.first_name} {lease.tenant.last_name}",
                        "email": lease.tenant.email,
                        "phone": lease.tenant.phone,
                    } if lease.tenant else None,
                    "unit": {
                        "id": str(lease.unit.id),
                        "unit_number": lease.unit.unit_number,
                        "type": lease.unit.unit_type.value,
                        "building": lease.unit.building.name if lease.unit.building else None,
                        "location": lease.unit.building.area if lease.unit.building else None,
                    } if lease.unit else None,
                })

            return json.dumps({
                "leases": results,
                "count": len(results),
                "days_ahead": days_ahead,
                "summary": {
                    "urgent": sum(1 for r in results if r["days_remaining"] <= 30),
                    "within_60_days": sum(1 for r in results if r["days_remaining"] <= 60),
                    "rera_notice_overdue": sum(1 for r in results if not r["rera_notice_window_open"]),
                },
            })

        except Exception as exc:
            return json.dumps({"error": f"view_expiring_leases failed: {exc}"})

    # ── TOOL 8: knowledge_search (RAG) ────────────────────────────────────

    @tool("knowledge_search", args_schema=KnowledgeSearchInput)
    async def knowledge_search(
        query: str,
        source: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> str:
        """
        Search the knowledge base using semantic similarity and return formatted context.
        Use this tool FIRST when the user asks about:
        - Lease policies (creation, termination, documents, blacklist, Ejari)
        - Tenant FAQs (DEWA, pets, parking, alterations, building rules)
        - Move-in guidelines (checklist, inspection, key handover, setup)
        - Move-out guidelines (notice, inspection, handover, Ejari cancellation)
        - Renewal policies (RERA 90-day notice, rent increase caps, renewal process)
        Optionally filter by source (lease_policies | tenant_faq | move_in_guidelines
        | move_out_guidelines | renewal_policies) for higher precision.
        """
        try:
            retriever = RAGRetriever(qdrant)
            result = await retriever.retrieve(
                query,
                source=source,
                doc_type=doc_type,
                top_k=4,
            )
            return json.dumps({
                "context": result["context"],
                "sources": result["sources"],
                "count": result["count"],
            })

        except Exception as exc:
            return json.dumps({"error": f"knowledge_search failed: {exc}"})

    # ── Tool registry ─────────────────────────────────────────────────────

    return [
        search_properties,
        search_tenant,
        create_lease,
        view_lease,
        renew_lease,
        create_maintenance_request,
        view_expiring_leases,
        knowledge_search,
    ]
