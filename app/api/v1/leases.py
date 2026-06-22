"""
app/api/v1/leases.py
---------------------
CRUD endpoints for leases.

Routes
───────
GET    /leases                  — list with filters (status, tenant_id, unit_id)
POST   /leases                  — create draft lease
GET    /leases/expiring         — renewal pipeline (active, ending soon)
GET    /leases/{id}             — full detail with nested tenant + unit
PATCH  /leases/{id}             — partial update (status transitions, Ejari)
POST   /leases/{id}/terminate   — convenience action to terminate a lease
"""

import uuid

from fastapi import APIRouter, Query, status

from app.dependencies import DBSession
from app.models.lease import LeaseStatus
from app.schemas.common import MessageResponse
from app.schemas.lease import LeaseCreate, LeaseDetail, LeaseRead, LeaseUpdate
from app.services.lease_service import LeaseService

router = APIRouter(prefix="/leases", tags=["Leases"])


@router.get("", response_model=list[LeaseRead], summary="List leases")
async def list_leases(
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    lease_status: LeaseStatus | None = Query(None, alias="status"),
    tenant_id: uuid.UUID | None = Query(None),
    unit_id: uuid.UUID | None = Query(None),
):
    """
    Returns leases with optional filters.
    Use tenant_id or unit_id to narrow results without a separate sub-resource call.
    """
    svc = LeaseService(db)
    return await svc.list_leases(
        skip=skip,
        limit=limit,
        lease_status=lease_status,
        tenant_id=tenant_id,
        unit_id=unit_id,
    )


@router.post("", response_model=LeaseRead, status_code=status.HTTP_201_CREATED, summary="Create lease")
async def create_lease(data: LeaseCreate, db: DBSession):
    """
    Creates a lease in DRAFT status.
    Validates: unit is available, tenant is not blacklisted.
    Sets unit status to RESERVED until the lease is activated.
    """
    svc = LeaseService(db)
    return await svc.create_lease(data)


# ── Static sub-paths BEFORE /{lease_id} ──────────────────────────────────

@router.get(
    "/expiring",
    response_model=list[LeaseRead],
    summary="Leases expiring soon (renewal pipeline)",
)
async def expiring_leases(
    db: DBSession,
    days_ahead: int = Query(180, ge=1, le=365, description="Look-ahead window in days."),
):
    """
    Returns active leases ending within `days_ahead` days.
    Used to drive the renewal workflow and 90-day RERA notice cron.
    """
    svc = LeaseService(db)
    return await svc.get_expiring_leases(days_ahead)


# ── Dynamic paths ─────────────────────────────────────────────────────────

@router.get("/{lease_id}", response_model=LeaseDetail, summary="Get lease detail")
async def get_lease(lease_id: uuid.UUID, db: DBSession):
    """
    Returns full lease detail including nested tenant and unit (with building).
    Loaded via joinedload — single DB round-trip.
    """
    svc = LeaseService(db)
    return await svc.get_lease(lease_id)


@router.patch("/{lease_id}", response_model=LeaseRead, summary="Update lease")
async def update_lease(lease_id: uuid.UUID, data: LeaseUpdate, db: DBSession):
    """
    Partial update. Key status transitions:
    - draft → active  : sets unit status to OCCUPIED
    - active → terminated / expired : sets unit status to AVAILABLE
    """
    svc = LeaseService(db)
    return await svc.update_lease(lease_id, data)


@router.post(
    "/{lease_id}/terminate",
    response_model=MessageResponse,
    summary="Terminate lease",
)
async def terminate_lease(lease_id: uuid.UUID, db: DBSession):
    """
    Convenience endpoint to set status = terminated.
    Equivalent to PATCH with {"status": "terminated"}.
    Unit is freed (status → available) in the same transaction.
    """
    svc = LeaseService(db)
    await svc.terminate_lease(lease_id)
    return MessageResponse(message="Lease terminated. Unit is now available.")
