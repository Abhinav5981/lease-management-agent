"""
app/agent/tools.py
-------------------
LangGraph tools for the FastAPI-integrated agent.

Key differences from the standalone agent/tools.py:
• Uses SQLAlchemy services (LeaseService, MaintenanceService, RenewalService)
  instead of raw asyncpg queries.
• Uses QdrantService for knowledge_search (RAG).
• Session and Qdrant client are injected at tool creation time via
  build_tools(session, qdrant) — a factory pattern that allows per-request
  database sessions to flow into the tools without global state.
"""

import json
from datetime import date
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


# ── Input schemas ──────────────────────────────────────────────────────────

class SearchPropertiesInput(BaseModel):
    location: Optional[str] = Field(None, description="Dubai area, e.g. 'Dubai Marina'.")
    unit_type: Optional[str] = Field(None, description="studio | 1br | 2br | 3br | 4br | penthouse.")
    bedrooms: Optional[int] = Field(None, description="Number of bedrooms (0 for studio).")


class SearchTenantsInput(BaseModel):
    query: str = Field(description="Name, email, phone, or Emirates ID.")


class CreateLeaseInput(BaseModel):
    unit_id: str = Field(description="UUID of the unit.")
    tenant_id: str = Field(description="UUID of the tenant.")
    start_date: str = Field(description="YYYY-MM-DD")
    end_date: str = Field(description="YYYY-MM-DD")
    annual_rent_aed: float = Field(description="Annual rent in AED (lease term only).")


class ViewLeaseInput(BaseModel):
    lease_ref: str = Field(description="Lease UUID or lease number e.g. LSE-2026-001042.")


class RenewLeaseInput(BaseModel):
    lease_id: str = Field(description="UUID of the expiring lease.")
    new_end_date: str = Field(description="YYYY-MM-DD")
    proposed_rent_aed: float = Field(description="Proposed annual rent in AED.")


class CreateMaintenanceInput(BaseModel):
    unit_id: str = Field(description="UUID of the unit.")
    tenant_id: str = Field(description="UUID of the tenant.")
    category: str = Field(description="hvac | plumbing | electrical | carpentry | painting | appliances | pest_control | cleaning | general.")
    priority: str = Field(description="emergency | high | medium | low.")
    title: str = Field(description="Short title (max 255 chars).")
    description: Optional[str] = Field(None, description="Detailed description.")


class ViewMaintenanceInput(BaseModel):
    unit_id: Optional[str] = Field(None, description="Filter by unit UUID.")
    tenant_id: Optional[str] = Field(None, description="Filter by tenant UUID.")
    status: Optional[str] = Field(None, description="open | assigned | in_progress | completed | cancelled.")


class ScheduleMoveOutInput(BaseModel):
    lease_id: str = Field(description="UUID of the lease being terminated.")
    inspection_date: str = Field(description="YYYY-MM-DD")
    notes: Optional[str] = Field(None, description="Special instructions.")


class KnowledgeSearchInput(BaseModel):
    query: str = Field(description="Natural language question about lease policies or RERA regulations.")
    doc_type: Optional[str] = Field(None, description="regulation | policy | faq | unit_description.")


# ── Tool factory ───────────────────────────────────────────────────────────

def build_tools(session: AsyncSession, qdrant: QdrantService) -> list:
    """
    Create the tool list bound to the given DB session and Qdrant service.
    Called once per agent invocation so each request gets its own session.
    """

    @tool("search_properties", args_schema=SearchPropertiesInput)
    async def search_properties(
        location: Optional[str] = None,
        unit_type: Optional[str] = None,
        bedrooms: Optional[int] = None,
    ) -> str:
        """Search for available units by location, type, or bedrooms."""
        try:
            from app.models.unit import UnitType
            repo = UnitRepository(session)
            ut = UnitType(unit_type) if unit_type else None
            units = await repo.search_available(
                area=location, unit_type=ut, bedrooms=bedrooms
            )
            results = [
                {
                    "id": str(u.id),
                    "unit_number": u.unit_number,
                    "floor": u.floor_number,
                    "type": u.unit_type.value,
                    "bedrooms": u.bedrooms,
                    "area_sqft": float(u.area_sqft),
                    "building": u.building.name if u.building else None,
                    "location": u.building.area if u.building else None,
                }
                for u in units
            ]
            return json.dumps({"units": results, "count": len(results)})
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @tool("search_tenants", args_schema=SearchTenantsInput)
    async def search_tenants(query: str) -> str:
        """Search tenants by name, email, phone, or Emirates ID."""
        try:
            repo = TenantRepository(session)
            tenants = await repo.search(query)
            results = [
                {
                    "id": str(t.id),
                    "name": f"{t.first_name} {t.last_name}",
                    "email": t.email,
                    "phone": t.phone,
                    "emirates_id": t.emirates_id,
                    "is_blacklisted": t.is_blacklisted,
                    "visa_expiry": t.visa_expiry.isoformat() if t.visa_expiry else None,
                }
                for t in tenants
            ]
            return json.dumps({"tenants": results, "count": len(results)})
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @tool("create_lease", args_schema=CreateLeaseInput)
    async def create_lease(
        unit_id: str,
        tenant_id: str,
        start_date: str,
        end_date: str,
        annual_rent_aed: float,
    ) -> str:
        """Create a new lease in DRAFT status after validating unit and tenant."""
        try:
            import uuid
            from decimal import Decimal
            from app.schemas.lease import LeaseCreate
            svc = LeaseService(session)
            lease = await svc.create_lease(
                LeaseCreate(
                    unit_id=uuid.UUID(unit_id),
                    tenant_id=uuid.UUID(tenant_id),
                    start_date=date.fromisoformat(start_date),
                    end_date=date.fromisoformat(end_date),
                    annual_rent_aed=Decimal(str(annual_rent_aed)),
                )
            )
            await session.commit()
            return json.dumps({
                "success": True,
                "lease_id": str(lease.id),
                "lease_number": lease.lease_number,
                "status": lease.status.value,
                "next_step": "Send for digital signing, then register with Ejari within 30 days.",
            })
        except Exception as exc:
            await session.rollback()
            return json.dumps({"error": str(exc)})

    @tool("view_lease", args_schema=ViewLeaseInput)
    async def view_lease(lease_ref: str) -> str:
        """Retrieve full lease details by UUID or lease number."""
        try:
            import uuid as _uuid
            repo = LeaseRepository(session)
            lease = None
            try:
                lease = await repo.get_with_details(_uuid.UUID(lease_ref))
            except ValueError:
                lease = await repo.get_by_lease_number(lease_ref)
            if not lease:
                return json.dumps({"error": f"Lease not found: {lease_ref}"})
            return json.dumps({
                "lease": {
                    "id": str(lease.id),
                    "lease_number": lease.lease_number,
                    "status": lease.status.value,
                    "start_date": lease.start_date.isoformat(),
                    "end_date": lease.end_date.isoformat(),
                    "annual_rent_aed": float(lease.annual_rent_aed),
                    "ejari_number": lease.ejari_number,
                    "tenant": f"{lease.tenant.first_name} {lease.tenant.last_name}" if lease.tenant else None,
                    "unit": lease.unit.unit_number if lease.unit else None,
                    "building": lease.unit.building.name if lease.unit and lease.unit.building else None,
                }
            })
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @tool("renew_lease", args_schema=RenewLeaseInput)
    async def renew_lease(
        lease_id: str,
        new_end_date: str,
        proposed_rent_aed: float,
    ) -> str:
        """Initiate a RERA-compliant renewal offer for an expiring lease."""
        try:
            import uuid
            from decimal import Decimal
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
            return json.dumps({
                "success": True,
                "renewal_id": str(renewal.id),
                "status": renewal.status.value,
                "notice_due_by": renewal.notice_due_by.isoformat(),
                "rera_notice_compliant": renewal.rera_notice_compliant,
                "previous_rent_aed": float(renewal.previous_rent_aed),
                "proposed_rent_aed": float(renewal.proposed_rent_aed),
            })
        except Exception as exc:
            await session.rollback()
            return json.dumps({"error": str(exc)})

    @tool("create_maintenance_request", args_schema=CreateMaintenanceInput)
    async def create_maintenance_request(
        unit_id: str,
        tenant_id: str,
        category: str,
        priority: str,
        title: str,
        description: Optional[str] = None,
    ) -> str:
        """Log a maintenance request with auto-calculated SLA deadline."""
        try:
            import uuid
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
            return json.dumps({
                "success": True,
                "reference_number": req.reference_number,
                "status": req.status.value,
                "priority": req.priority.value,
                "sla_due_at": req.sla_due_at.isoformat() if req.sla_due_at else None,
            })
        except Exception as exc:
            await session.rollback()
            return json.dumps({"error": str(exc)})

    @tool("view_maintenance_requests", args_schema=ViewMaintenanceInput)
    async def view_maintenance_requests(
        unit_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> str:
        """List maintenance requests filtered by unit, tenant, and/or status."""
        try:
            import uuid
            from app.models.maintenance import MaintenanceStatus
            svc = MaintenanceService(session)
            requests = []
            if unit_id:
                st = MaintenanceStatus(status) if status else None
                requests = await svc.list_for_unit(uuid.UUID(unit_id), status=st)
            elif tenant_id:
                st = MaintenanceStatus(status) if status else None
                requests = await svc.list_for_tenant(uuid.UUID(tenant_id), status=st)
            results = [
                {
                    "id": str(r.id),
                    "reference_number": r.reference_number,
                    "category": r.category.value,
                    "priority": r.priority.value,
                    "status": r.status.value,
                    "title": r.title,
                    "sla_due_at": r.sla_due_at.isoformat() if r.sla_due_at else None,
                    "reported_at": r.reported_at.isoformat(),
                }
                for r in requests
            ]
            return json.dumps({"requests": results, "count": len(results)})
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    @tool("schedule_move_out_inspection", args_schema=ScheduleMoveOutInput)
    async def schedule_move_out_inspection(
        lease_id: str,
        inspection_date: str,
        notes: Optional[str] = None,
    ) -> str:
        """Schedule a move-out inspection by creating a maintenance request."""
        try:
            import uuid
            from app.models.maintenance import MaintenanceCategory, MaintenancePriority
            from app.schemas.maintenance import MaintenanceRequestCreate
            repo = LeaseRepository(session)
            lease = await repo.get_with_details(uuid.UUID(lease_id))
            if not lease:
                return json.dumps({"error": "Lease not found."})
            svc = MaintenanceService(session)
            req = await svc.create_request(
                MaintenanceRequestCreate(
                    unit_id=lease.unit_id,
                    tenant_id=lease.tenant_id,
                    category=MaintenanceCategory.GENERAL,
                    priority=MaintenancePriority.MEDIUM,
                    title=f"Move-out Inspection — {inspection_date}",
                    description=(
                        f"Scheduled: {inspection_date}. "
                        f"Lease ends: {lease.end_date.isoformat()}."
                        + (f" Notes: {notes}" if notes else "")
                    ),
                )
            )
            await session.commit()
            return json.dumps({
                "success": True,
                "reference_number": req.reference_number,
                "inspection_date": inspection_date,
                "lease_end_date": lease.end_date.isoformat(),
            })
        except Exception as exc:
            await session.rollback()
            return json.dumps({"error": str(exc)})

    @tool("knowledge_search", args_schema=KnowledgeSearchInput)
    async def knowledge_search(
        query: str, doc_type: Optional[str] = None
    ) -> str:
        """Search RERA regulations and company policies using semantic similarity."""
        try:
            results = await qdrant.search(query, top_k=4, doc_type=doc_type)
            if not results:
                return json.dumps({"results": [], "message": "No relevant documents found."})
            return json.dumps({
                "results": [
                    {"text": r["text"], "source": r["source"], "score": round(r["score"], 3)}
                    for r in results
                ]
            })
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    return [
        search_properties,
        search_tenants,
        create_lease,
        view_lease,
        renew_lease,
        create_maintenance_request,
        view_maintenance_requests,
        schedule_move_out_inspection,
        knowledge_search,
    ]
