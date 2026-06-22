"""
app/api/v1/maintenance.py
--------------------------
CRUD endpoints for maintenance requests.

Routes
───────
GET    /maintenance                        — list with filters (status, priority, category)
POST   /maintenance                        — create (auto SLA + lease resolution)
GET    /maintenance/sla-breached           — all open requests past their SLA deadline
GET    /maintenance/unit/{unit_id}         — requests for a specific unit
GET    /maintenance/tenant/{tenant_id}     — requests raised by a specific tenant
GET    /maintenance/{id}                   — full detail with nested tenant + unit
PATCH  /maintenance/{id}                   — update (assignment, status, resolution)
DELETE /maintenance/{id}                   — cancel request
"""

import uuid

from fastapi import APIRouter, Body, Query, status

from app.dependencies import DBSession
from app.models.maintenance import MaintenanceCategory, MaintenancePriority, MaintenanceStatus
from app.schemas.common import MessageResponse
from app.schemas.maintenance import (
    MaintenanceRequestCreate,
    MaintenanceRequestDetail,
    MaintenanceRequestRead,
    MaintenanceRequestUpdate,
)
from app.services.maintenance_service import MaintenanceService

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


@router.get("", response_model=list[MaintenanceRequestRead], summary="List maintenance requests")
async def list_maintenance(
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    req_status: MaintenanceStatus | None = Query(None, alias="status"),
    priority: MaintenancePriority | None = Query(None),
    category: MaintenanceCategory | None = Query(None),
):
    svc = MaintenanceService(db)
    return await svc.list_all(
        skip=skip,
        limit=limit,
        req_status=req_status,
        priority=priority,
        category=category.value if category else None,
    )


@router.post("", response_model=MaintenanceRequestRead, status_code=status.HTTP_201_CREATED, summary="Create maintenance request")
async def create_request(data: MaintenanceRequestCreate, db: DBSession):
    """
    Creates and triages a maintenance request.
    SLA deadline is auto-calculated from priority:
    emergency=1h │ high=6h │ medium=48h │ low=120h.
    Active lease is resolved automatically.
    """
    svc = MaintenanceService(db)
    return await svc.create_request(data)


# ── Static sub-paths BEFORE /{request_id} ────────────────────────────────

@router.get(
    "/sla-breached",
    response_model=list[MaintenanceRequestRead],
    summary="Requests past SLA deadline",
)
async def sla_breached_requests(db: DBSession):
    """
    Returns all open/in-progress requests whose sla_due_at has passed.
    Used by the operations dashboard and the agent’s SLA monitoring cron.
    """
    svc = MaintenanceService(db)
    return await svc.get_sla_breached()


@router.get(
    "/unit/{unit_id}",
    response_model=list[MaintenanceRequestRead],
    summary="Requests for a unit",
)
async def list_by_unit(
    unit_id: uuid.UUID,
    db: DBSession,
    req_status: MaintenanceStatus | None = Query(None, alias="status"),
):
    svc = MaintenanceService(db)
    return await svc.list_for_unit(unit_id, status=req_status)


@router.get(
    "/tenant/{tenant_id}",
    response_model=list[MaintenanceRequestRead],
    summary="Requests raised by a tenant",
)
async def list_by_tenant(
    tenant_id: uuid.UUID,
    db: DBSession,
    req_status: MaintenanceStatus | None = Query(None, alias="status"),
):
    svc = MaintenanceService(db)
    return await svc.list_for_tenant(tenant_id, status=req_status)


# ── Dynamic paths ─────────────────────────────────────────────────────────

@router.get(
    "/{request_id}",
    response_model=MaintenanceRequestDetail,
    summary="Get maintenance request detail",
)
async def get_request(request_id: uuid.UUID, db: DBSession):
    """Returns request detail with nested tenant and unit (with building)."""
    svc = MaintenanceService(db)
    return await svc.get_request(request_id)


@router.patch(
    "/{request_id}",
    response_model=MaintenanceRequestRead,
    summary="Update maintenance request",
)
async def update_request(
    request_id: uuid.UUID,
    data: MaintenanceRequestUpdate,
    db: DBSession,
):
    """
    Update assignment, status, resolution notes, or tenant rating.
    Setting status=completed auto-populates completed_at.
    """
    svc = MaintenanceService(db)
    return await svc.update_request(request_id, data)


@router.delete(
    "/{request_id}",
    response_model=MessageResponse,
    summary="Cancel maintenance request",
)
async def cancel_request(
    request_id: uuid.UUID,
    db: DBSession,
    reason: str | None = Body(None, embed=True, description="Optional cancellation reason."),
):
    """
    Cancels an open or in-progress request.
    Cannot cancel requests that are already completed or cancelled.
    """
    svc = MaintenanceService(db)
    await svc.cancel_request(request_id, reason=reason)
    return MessageResponse(message="Maintenance request cancelled.")
