"""
agent/tools.py
--------------
Eight tools exposed to the LangGraph agent via LangChain function-calling.

Tool design principles
───────────────────────
• Every tool is async — pairs with the async LangGraph graph and asyncpg pool.
• Every tool returns a JSON string — the LLM reads structured output reliably.
• Errors are returned as {"error": "..."} dicts, never raised as exceptions.
  This lets the LLM reason about failures and suggest corrective action rather
  than crashing the ReAct loop.
• Input schemas use Pydantic so LangChain auto-generates the JSON schema that
  the LLM sees in its tool manifest.
• Queries use $N parameters throughout — no string interpolation, no SQL injection.
"""

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

import asyncpg
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from .db import get_pool

# ── SLA map (hours) ────────────────────────────────────────────────────────
_SLA_HOURS: dict[str, int] = {
    "emergency": 1,
    "high": 6,
    "medium": 48,
    "low": 120,   # 5 business days approximated
}


# ── Helpers ────────────────────────────────────────────────────────────────

def _serialize(record: asyncpg.Record) -> dict:
    """Convert an asyncpg Record to a JSON-serialisable dict."""
    result: dict = {}
    for key, value in record.items():
        if isinstance(value, (date, datetime)):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        elif isinstance(value, UUID):
            result[key] = str(value)
        else:
            result[key] = value
    return result


def _lease_number() -> str:
    return f"LSE-{date.today().year}-{str(uuid4().int)[:6].zfill(6)}"


def _maint_ref() -> str:
    return f"MR-{date.today().year}-{str(uuid4().int)[:6].zfill(6)}"


# ══════════════════════════════════════════════════════════════════════════
# INPUT SCHEMAS
# ══════════════════════════════════════════════════════════════════════════

class SearchPropertiesInput(BaseModel):
    location: Optional[str] = Field(
        None, description="Dubai area, e.g. 'Dubai Marina', 'JBR', 'Downtown Dubai'."
    )
    unit_type: Optional[str] = Field(
        None, description="One of: studio | 1br | 2br | 3br | 4br | penthouse."
    )
    bedrooms: Optional[int] = Field(
        None, description="Number of bedrooms (use 0 for studio)."
    )
    max_rent_aed: Optional[float] = Field(
        None, description="Maximum annual rent in AED."
    )


class SearchTenantsInput(BaseModel):
    query: str = Field(
        description="Search by full or partial name, email address, phone number, or Emirates ID."
    )


class CreateLeaseInput(BaseModel):
    unit_id: str = Field(description="UUID of the unit to be leased.")
    tenant_id: str = Field(description="UUID of the tenant signing the lease.")
    start_date: str = Field(description="Lease start date — YYYY-MM-DD.")
    end_date: str = Field(description="Lease end date — YYYY-MM-DD.")
    annual_rent_aed: float = Field(
        description="Agreed annual rent in AED (lease term for RERA compliance — not a payment instruction)."
    )


class ViewLeaseInput(BaseModel):
    lease_ref: str = Field(
        description="Lease UUID or human-readable lease number, e.g. LSE-2026-001042."
    )


class RenewLeaseInput(BaseModel):
    lease_id: str = Field(description="UUID of the expiring lease to renew.")
    new_end_date: str = Field(description="Proposed new lease end date — YYYY-MM-DD.")
    proposed_rent_aed: float = Field(
        description="Proposed annual rent for the renewed term in AED."
    )


class CreateMaintenanceInput(BaseModel):
    unit_id: str = Field(description="UUID of the unit with the issue.")
    tenant_id: str = Field(description="UUID of the tenant raising the request.")
    category: str = Field(
        description="Category: hvac | plumbing | electrical | carpentry | painting | appliances | pest_control | cleaning | general."
    )
    priority: str = Field(
        description="Priority: emergency | high | medium | low."
    )
    title: str = Field(description="Short descriptive title (max 255 characters).")
    description: Optional[str] = Field(
        None, description="Detailed description of the issue."
    )


class ViewMaintenanceInput(BaseModel):
    unit_id: Optional[str] = Field(None, description="Filter by unit UUID.")
    tenant_id: Optional[str] = Field(None, description="Filter by tenant UUID.")
    status: Optional[str] = Field(
        None,
        description="Filter by status: open | assigned | in_progress | pending_tenant_confirmation | completed | cancelled.",
    )


class ScheduleMoveOutInput(BaseModel):
    lease_id: str = Field(description="UUID of the lease being terminated.")
    inspection_date: str = Field(
        description="Preferred move-out inspection date — YYYY-MM-DD."
    )
    notes: Optional[str] = Field(
        None, description="Special instructions for the inspection team."
    )


# ══════════════════════════════════════════════════════════════════════════
# TOOL 1 — search_properties
# ══════════════════════════════════════════════════════════════════════════

@tool("search_properties", args_schema=SearchPropertiesInput)
async def search_properties(
    location: Optional[str] = None,
    unit_type: Optional[str] = None,
    bedrooms: Optional[int] = None,
    max_rent_aed: Optional[float] = None,
) -> str:
    """Search for available units in the portfolio by location, type, bedrooms, or max rent."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    u.id,
                    u.unit_number,
                    u.floor_number,
                    u.unit_type,
                    u.bedrooms,
                    u.bathrooms,
                    u.area_sqft,
                    u.status,
                    b.name AS building_name,
                    b.area AS location
                FROM units u
                JOIN buildings b ON b.id = u.building_id
                WHERE u.status = 'available'
                  AND b.is_active = TRUE
                  AND ($1::text IS NULL OR b.area ILIKE '%' || $1 || '%')
                  AND ($2::text IS NULL OR u.unit_type::text = $2)
                  AND ($3::int  IS NULL OR u.bedrooms = $3)
                ORDER BY u.area_sqft
                LIMIT 20
                """,
                location,
                unit_type,
                bedrooms,
            )

        results = [_serialize(r) for r in rows]
        if not results:
            return json.dumps(
                {"units": [], "message": "No available units match the search criteria."}
            )
        return json.dumps({"units": results, "count": len(results)})

    except Exception as exc:
        return json.dumps({"error": f"search_properties failed: {exc}"})


# ══════════════════════════════════════════════════════════════════════════
# TOOL 2 — search_tenants
# ══════════════════════════════════════════════════════════════════════════

@tool("search_tenants", args_schema=SearchTenantsInput)
async def search_tenants(query: str) -> str:
    """Search for tenants by name, email, phone, or Emirates ID."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    first_name,
                    last_name,
                    email,
                    phone,
                    nationality,
                    emirates_id,
                    passport_expiry,
                    emirates_id_expiry,
                    visa_expiry,
                    is_blacklisted
                FROM tenants
                WHERE is_active = TRUE
                  AND (
                       first_name ILIKE '%' || $1 || '%'
                    OR last_name  ILIKE '%' || $1 || '%'
                    OR (first_name || ' ' || last_name) ILIKE '%' || $1 || '%'
                    OR email       = $1
                    OR phone       = $1
                    OR emirates_id = $1
                  )
                ORDER BY last_name, first_name
                LIMIT 10
                """,
                query,
            )

        results = [_serialize(r) for r in rows]
        if not results:
            return json.dumps(
                {"tenants": [], "message": "No tenants found matching that query."}
            )
        return json.dumps({"tenants": results, "count": len(results)})

    except Exception as exc:
        return json.dumps({"error": f"search_tenants failed: {exc}"})


# ══════════════════════════════════════════════════════════════════════════
# TOOL 3 — create_lease
# ══════════════════════════════════════════════════════════════════════════

@tool("create_lease", args_schema=CreateLeaseInput)
async def create_lease(
    unit_id: str,
    tenant_id: str,
    start_date: str,
    end_date: str,
    annual_rent_aed: float,
) -> str:
    """
    Create a new lease in 'draft' status after confirming unit availability and
    tenant eligibility. The lease must be sent for digital signing to become active.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:

            # Guard: unit must exist and be available
            unit = await conn.fetchrow(
                "SELECT id, unit_number, status FROM units WHERE id = $1::uuid",
                unit_id,
            )
            if not unit:
                return json.dumps({"error": "Unit not found."})
            if unit["status"] != "available":
                return json.dumps(
                    {
                        "error": (
                            f"Unit {unit['unit_number']} is not available "
                            f"(current status: {unit['status']})."
                        )
                    }
                )

            # Guard: tenant must exist and not be blacklisted
            tenant = await conn.fetchrow(
                "SELECT id, first_name, last_name, is_blacklisted FROM tenants WHERE id = $1::uuid",
                tenant_id,
            )
            if not tenant:
                return json.dumps({"error": "Tenant not found."})
            if tenant["is_blacklisted"]:
                return json.dumps(
                    {"error": "Tenant is blacklisted and cannot sign a new lease."}
                )

            # Create the lease
            lease_number = _lease_number()
            row = await conn.fetchrow(
                """
                INSERT INTO leases (
                    lease_number, unit_id, tenant_id,
                    start_date, end_date, annual_rent_aed, status
                )
                VALUES ($1, $2::uuid, $3::uuid, $4::date, $5::date, $6, 'draft')
                RETURNING id, lease_number, status, start_date, end_date, annual_rent_aed
                """,
                lease_number,
                unit_id,
                tenant_id,
                start_date,
                end_date,
                annual_rent_aed,
            )

            # Mark unit as reserved so no parallel lease can be created
            await conn.execute(
                "UPDATE units SET status = 'reserved' WHERE id = $1::uuid",
                unit_id,
            )

        return json.dumps(
            {
                "success": True,
                "lease": _serialize(row),
                "next_step": (
                    "Lease created in DRAFT status. "
                    "Send the contract to both parties for digital signing, "
                    "then register with Ejari within 30 days of signing."
                ),
            }
        )

    except Exception as exc:
        return json.dumps({"error": f"create_lease failed: {exc}"})


# ══════════════════════════════════════════════════════════════════════════
# TOOL 4 — view_lease
# ══════════════════════════════════════════════════════════════════════════

@tool("view_lease", args_schema=ViewLeaseInput)
async def view_lease(lease_ref: str) -> str:
    """Retrieve full details of a lease by UUID or lease number (e.g. LSE-2026-001042)."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    l.id,
                    l.lease_number,
                    l.status,
                    l.start_date,
                    l.end_date,
                    l.annual_rent_aed,
                    l.notice_period_days,
                    l.ejari_number,
                    l.ejari_registration_date,
                    l.signed_by_tenant_at,
                    l.signed_by_company_at,
                    t.id                          AS tenant_id,
                    t.first_name || ' ' || t.last_name AS tenant_name,
                    t.email                       AS tenant_email,
                    t.phone                       AS tenant_phone,
                    t.emirates_id,
                    t.visa_expiry,
                    u.id                          AS unit_id,
                    u.unit_number,
                    u.unit_type,
                    u.floor_number,
                    b.name                        AS building_name,
                    b.area                        AS location
                FROM leases l
                JOIN tenants   t ON t.id = l.tenant_id
                JOIN units     u ON u.id = l.unit_id
                JOIN buildings b ON b.id = u.building_id
                WHERE l.id::text = $1
                   OR l.lease_number = $1
                """,
                lease_ref,
            )

        if not row:
            return json.dumps(
                {"error": f"No lease found for reference '{lease_ref}'."}
            )

        return json.dumps({"lease": _serialize(row)})

    except Exception as exc:
        return json.dumps({"error": f"view_lease failed: {exc}"})


# ══════════════════════════════════════════════════════════════════════════
# TOOL 5 — renew_lease
# ══════════════════════════════════════════════════════════════════════════

@tool("renew_lease", args_schema=RenewLeaseInput)
async def renew_lease(
    lease_id: str,
    new_end_date: str,
    proposed_rent_aed: float,
) -> str:
    """
    Initiate a lease renewal offer. Computes the RERA 90-day notice deadline
    and flags compliance status. Creates a renewal record in 'offered' status.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:

            lease = await conn.fetchrow(
                """
                SELECT id, tenant_id, unit_id, end_date, annual_rent_aed, status
                FROM leases
                WHERE id = $1::uuid
                """,
                lease_id,
            )
            if not lease:
                return json.dumps({"error": "Lease not found."})
            if lease["status"] != "active":
                return json.dumps(
                    {
                        "error": (
                            f"Only active leases can be renewed "
                            f"(current status: {lease['status']})."
                        )
                    }
                )

            lease_end: date = lease["end_date"]
            today = date.today()
            notice_due_by: date = lease_end - timedelta(days=90)
            rera_compliant: bool = today <= notice_due_by
            new_start: date = lease_end + timedelta(days=1)

            # Prevent duplicate open renewals
            existing = await conn.fetchrow(
                """
                SELECT id FROM renewals
                WHERE lease_id = $1::uuid
                  AND status IN ('pending', 'offered', 'negotiating')
                """,
                lease_id,
            )
            if existing:
                return json.dumps(
                    {
                        "error": "An open renewal already exists for this lease.",
                        "renewal_id": str(existing["id"]),
                    }
                )

            row = await conn.fetchrow(
                """
                INSERT INTO renewals (
                    lease_id, tenant_id, unit_id,
                    new_start_date, new_end_date,
                    previous_rent_aed, proposed_rent_aed,
                    notice_due_by, rera_notice_compliant,
                    status
                )
                VALUES (
                    $1::uuid, $2::uuid, $3::uuid,
                    $4::date, $5::date,
                    $6, $7,
                    $8::date, $9,
                    'offered'
                )
                RETURNING id, status, notice_due_by, rera_notice_compliant
                """,
                lease_id,
                str(lease["tenant_id"]),
                str(lease["unit_id"]),
                new_start.isoformat(),
                new_end_date,
                float(lease["annual_rent_aed"]),
                proposed_rent_aed,
                notice_due_by.isoformat(),
                rera_compliant,
            )

        compliance_warning = (
            ""
            if rera_compliant
            else (
                f" WARNING: Notice deadline was {notice_due_by.isoformat()} — "
                "already passed. This may be non-compliant with RERA Law 33."
            )
        )

        return json.dumps(
            {
                "success": True,
                "renewal": _serialize(row),
                "previous_rent_aed": float(lease["annual_rent_aed"]),
                "proposed_rent_aed": proposed_rent_aed,
                "rera_90_day_compliant": rera_compliant,
                "notice_due_by": notice_due_by.isoformat(),
                "message": (
                    f"Renewal offer created and set to 'offered'. "
                    f"Awaiting tenant response.{compliance_warning}"
                ),
            }
        )

    except Exception as exc:
        return json.dumps({"error": f"renew_lease failed: {exc}"})


# ══════════════════════════════════════════════════════════════════════════
# TOOL 6 — create_maintenance_request
# ══════════════════════════════════════════════════════════════════════════

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
    Log a new maintenance or repair request. Automatically calculates the SLA
    due timestamp from the priority level and resolves the active lease.
    """
    try:
        sla_hours = _SLA_HOURS.get(priority, 48)
        sla_due_at = datetime.now(timezone.utc) + timedelta(hours=sla_hours)
        ref_number = _maint_ref()

        pool = await get_pool()
        async with pool.acquire() as conn:

            # Resolve active lease (best-effort; nullable FK)
            lease = await conn.fetchrow(
                """
                SELECT id FROM leases
                WHERE unit_id = $1::uuid
                  AND tenant_id = $2::uuid
                  AND status = 'active'
                """,
                unit_id,
                tenant_id,
            )
            lease_id: Optional[str] = str(lease["id"]) if lease else None

            row = await conn.fetchrow(
                """
                INSERT INTO maintenance_requests (
                    reference_number, unit_id, lease_id, tenant_id,
                    category, priority, status,
                    title, description, sla_due_at
                )
                VALUES (
                    $1, $2::uuid, $3::uuid, $4::uuid,
                    $5::maintenance_category_enum,
                    $6::maintenance_priority_enum,
                    'open',
                    $7, $8, $9
                )
                RETURNING id, reference_number, status, priority, sla_due_at
                """,
                ref_number,
                unit_id,
                lease_id,
                tenant_id,
                category,
                priority,
                title,
                description,
                sla_due_at,
            )

        return json.dumps(
            {
                "success": True,
                "maintenance_request": _serialize(row),
                "sla_hours": sla_hours,
                "message": (
                    f"Request {ref_number} logged. "
                    f"SLA: respond within {sla_hours} hour(s)."
                ),
            }
        )

    except Exception as exc:
        return json.dumps({"error": f"create_maintenance_request failed: {exc}"})


# ══════════════════════════════════════════════════════════════════════════
# TOOL 7 — view_maintenance_requests
# ══════════════════════════════════════════════════════════════════════════

@tool("view_maintenance_requests", args_schema=ViewMaintenanceInput)
async def view_maintenance_requests(
    unit_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    """
    List maintenance requests filtered by unit, tenant, and/or status.
    Results are ordered by priority (emergency first) then most recent.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    mr.id,
                    mr.reference_number,
                    mr.category,
                    mr.priority,
                    mr.status,
                    mr.title,
                    mr.assigned_to,
                    mr.sla_due_at,
                    mr.reported_at,
                    mr.completed_at,
                    mr.tenant_rating,
                    u.unit_number,
                    b.name                         AS building_name,
                    t.first_name || ' ' || t.last_name AS tenant_name
                FROM maintenance_requests mr
                JOIN units     u ON u.id = mr.unit_id
                JOIN buildings b ON b.id = u.building_id
                JOIN tenants   t ON t.id = mr.tenant_id
                WHERE ($1::text IS NULL OR mr.unit_id::text   = $1)
                  AND ($2::text IS NULL OR mr.tenant_id::text = $2)
                  AND ($3::text IS NULL OR mr.status::text    = $3)
                ORDER BY
                    CASE mr.priority
                        WHEN 'emergency' THEN 1
                        WHEN 'high'      THEN 2
                        WHEN 'medium'    THEN 3
                        ELSE 4
                    END,
                    mr.reported_at DESC
                LIMIT 50
                """,
                unit_id,
                tenant_id,
                status,
            )

        results = [_serialize(r) for r in rows]
        if not results:
            return json.dumps(
                {"requests": [], "message": "No maintenance requests found."}
            )
        return json.dumps({"requests": results, "count": len(results)})

    except Exception as exc:
        return json.dumps({"error": f"view_maintenance_requests failed: {exc}"})


# ══════════════════════════════════════════════════════════════════════════
# TOOL 8 — schedule_move_out_inspection
# ══════════════════════════════════════════════════════════════════════════

@tool("schedule_move_out_inspection", args_schema=ScheduleMoveOutInput)
async def schedule_move_out_inspection(
    lease_id: str,
    inspection_date: str,
    notes: Optional[str] = None,
) -> str:
    """
    Schedule a move-out inspection for a lease before the tenant vacates.
    Stored as a maintenance request (MVP approach — a dedicated inspections
    table is recommended for production).
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:

            lease = await conn.fetchrow(
                """
                SELECT
                    l.id,
                    l.tenant_id,
                    l.unit_id,
                    l.end_date,
                    l.status,
                    u.unit_number,
                    b.name AS building_name,
                    t.first_name || ' ' || t.last_name AS tenant_name
                FROM leases    l
                JOIN units     u ON u.id = l.unit_id
                JOIN buildings b ON b.id = u.building_id
                JOIN tenants   t ON t.id = l.tenant_id
                WHERE l.id = $1::uuid
                """,
                lease_id,
            )
            if not lease:
                return json.dumps({"error": "Lease not found."})
            if lease["status"] not in ("active", "terminated"):
                return json.dumps(
                    {
                        "error": (
                            f"Move-out inspection requires an active or terminated lease "
                            f"(current status: {lease['status']})."
                        )
                    }
                )

            ref_number = _maint_ref()
            base_desc = (
                f"Move-out inspection scheduled for {inspection_date}. "
                f"Unit: {lease['unit_number']}, {lease['building_name']}. "
                f"Tenant: {lease['tenant_name']}. "
                f"Lease end: {lease['end_date'].isoformat()}."
            )
            full_desc = f"{base_desc} Notes: {notes}" if notes else base_desc

            row = await conn.fetchrow(
                """
                INSERT INTO maintenance_requests (
                    reference_number, unit_id, lease_id, tenant_id,
                    category, priority, status,
                    title, description
                )
                VALUES (
                    $1, $2::uuid, $3::uuid, $4::uuid,
                    'general', 'medium', 'open',
                    $5, $6
                )
                RETURNING id, reference_number, status
                """,
                ref_number,
                str(lease["unit_id"]),
                lease_id,
                str(lease["tenant_id"]),
                f"Move-out Inspection — {inspection_date}",
                full_desc,
            )

        return json.dumps(
            {
                "success": True,
                "inspection": {
                    "reference_number": row["reference_number"],
                    "lease_id": lease_id,
                    "unit": f"{lease['unit_number']}, {lease['building_name']}",
                    "tenant": lease["tenant_name"],
                    "scheduled_date": inspection_date,
                    "lease_end_date": lease["end_date"].isoformat(),
                    "status": row["status"],
                },
                "message": (
                    f"Move-out inspection scheduled for {inspection_date}. "
                    f"Ref: {row['reference_number']}."
                ),
            }
        )

    except Exception as exc:
        return json.dumps({"error": f"schedule_move_out_inspection failed: {exc}"})


# ── Tool registry (imported by graph.py) ───────────────────────────────────
ALL_TOOLS = [
    search_properties,
    search_tenants,
    create_lease,
    view_lease,
    renew_lease,
    create_maintenance_request,
    view_maintenance_requests,
    schedule_move_out_inspection,
]
