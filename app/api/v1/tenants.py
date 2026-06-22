"""
app/api/v1/tenants.py
----------------------
CRUD endpoints for tenants.

Routes
───────
GET    /tenants                         — list / search
POST   /tenants                         — create (dedup email check)
GET    /tenants/expiring-documents      — KYC expiry alert list
GET    /tenants/{id}                    — detail
PATCH  /tenants/{id}                    — partial update
DELETE /tenants/{id}                    — soft deactivate
GET    /tenants/{id}/leases             — all leases for this tenant
GET    /tenants/{id}/maintenance        — all maintenance requests for this tenant
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import DBSession
from app.models.maintenance import MaintenanceStatus
from app.repositories.tenant_repository import TenantRepository
from app.schemas.common import MessageResponse
from app.schemas.lease import LeaseRead
from app.schemas.maintenance import MaintenanceRequestRead
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate
from app.services.lease_service import LeaseService
from app.services.maintenance_service import MaintenanceService

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("", response_model=list[TenantRead], summary="List / search tenants")
async def list_tenants(
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(
        None, description="Search by full/partial name, email, phone, or Emirates ID."
    ),
):
    repo = TenantRepository(db)
    if q:
        return await repo.search(q)
    return await repo.get_all(skip=skip, limit=limit)


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED, summary="Create tenant")
async def create_tenant(data: TenantCreate, db: DBSession):
    repo = TenantRepository(db)
    if await repo.get_by_email(data.email):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A tenant with this email already exists."
        )
    return await repo.create(data.model_dump())


# ── Static paths BEFORE /{tenant_id} ─────────────────────────────────────

@router.get(
    "/expiring-documents",
    response_model=list[TenantRead],
    summary="Tenants with expiring KYC documents",
)
async def tenants_with_expiring_documents(
    db: DBSession,
    days_ahead: int = Query(30, ge=1, le=365, description="Alert window in days."),
):
    """
    Returns tenants whose passport, Emirates ID, or visa expires
    within the specified number of days. Used by the agent expiry-alert cron.
    """
    repo = TenantRepository(db)
    return await repo.get_expiring_documents(days_ahead)


# ── Dynamic paths ─────────────────────────────────────────────────────────

@router.get("/{tenant_id}", response_model=TenantRead, summary="Get tenant")
async def get_tenant(tenant_id: uuid.UUID, db: DBSession):
    repo = TenantRepository(db)
    tenant = await repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
    return tenant


@router.patch("/{tenant_id}", response_model=TenantRead, summary="Update tenant")
async def update_tenant(tenant_id: uuid.UUID, data: TenantUpdate, db: DBSession):
    repo = TenantRepository(db)
    updated = await repo.update(tenant_id, data.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
    return updated


@router.delete(
    "/{tenant_id}",
    response_model=MessageResponse,
    summary="Deactivate tenant",
)
async def deactivate_tenant(tenant_id: uuid.UUID, db: DBSession):
    """
    Soft-deletes a tenant by setting is_active = False.
    Does NOT terminate active leases — handle those separately.
    """
    repo = TenantRepository(db)
    updated = await repo.update(tenant_id, {"is_active": False})
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
    return MessageResponse(message="Tenant deactivated successfully.")


@router.get(
    "/{tenant_id}/leases",
    response_model=list[LeaseRead],
    summary="Get leases for tenant",
)
async def get_leases_for_tenant(tenant_id: uuid.UUID, db: DBSession):
    """Returns all leases (any status) associated with this tenant."""
    svc = LeaseService(db)
    return await svc.list_for_tenant(tenant_id)


@router.get(
    "/{tenant_id}/maintenance",
    response_model=list[MaintenanceRequestRead],
    summary="Get maintenance requests for tenant",
)
async def get_maintenance_for_tenant(
    tenant_id: uuid.UUID,
    db: DBSession,
    req_status: MaintenanceStatus | None = Query(None, alias="status"),
):
    """Returns maintenance requests raised by this tenant."""
    svc = MaintenanceService(db)
    return await svc.list_for_tenant(tenant_id, status=req_status)
