"""
app/services/maintenance_service.py
-------------------------------------
Business logic for maintenance request lifecycle.

Calculates SLA deadlines, resolves the active lease, and owns
the reference number generation.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.maintenance import MaintenanceRequest, MaintenancePriority, MaintenanceStatus
from app.models.unit import Unit
from app.repositories.maintenance_repository import MaintenanceRepository
from app.repositories.lease_repository import LeaseRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.tenant_repository import TenantRepository
from app.schemas.maintenance import MaintenanceRequestCreate, MaintenanceRequestUpdate

_SLA_HOURS: dict[MaintenancePriority, int] = {
    MaintenancePriority.EMERGENCY: 1,
    MaintenancePriority.HIGH: 6,
    MaintenancePriority.MEDIUM: 48,
    MaintenancePriority.LOW: 120,
}


def _generate_ref() -> str:
    import uuid as _uuid
    from datetime import date
    suffix = str(_uuid.uuid4().int)[:6].zfill(6)
    return f"MR-{date.today().year}-{suffix}"


class MaintenanceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MaintenanceRepository(session)
        self._leases = LeaseRepository(session)
        self._units = UnitRepository(session)
        self._tenants = TenantRepository(session)

    async def create_request(self, data: MaintenanceRequestCreate) -> MaintenanceRequest:
        unit = await self._units.get_by_id(data.unit_id)
        if not unit:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found.")

        tenant = await self._tenants.get_by_id(data.tenant_id)
        if not tenant:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")

        # Resolve active lease (best-effort; lease_id is nullable)
        active_lease = await self._leases.get_active_for_unit(data.unit_id)
        lease_id = active_lease.id if active_lease else None

        sla_hours = _SLA_HOURS[data.priority]
        sla_due_at = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

        return await self._repo.create(
            {
                **data.model_dump(),
                "lease_id": lease_id,
                "reference_number": _generate_ref(),
                "status": MaintenanceStatus.OPEN,
                "reported_at": datetime.now(timezone.utc),
                "sla_due_at": sla_due_at,
            }
        )

    async def get_request(self, request_id: uuid.UUID) -> MaintenanceRequest:
        req = await self._repo.get_by_id(request_id)
        if not req:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Maintenance request not found.")
        return req

    async def update_request(
        self, request_id: uuid.UUID, data: MaintenanceRequestUpdate
    ) -> MaintenanceRequest:
        req = await self._repo.get_by_id(request_id)
        if not req:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Maintenance request not found.")

        update_data = data.model_dump(exclude_none=True)

        if "status" in update_data and update_data["status"] == MaintenanceStatus.COMPLETED:
            if "completed_at" not in update_data:
                update_data["completed_at"] = datetime.now(timezone.utc)

        updated = await self._repo.update(request_id, update_data)
        return updated

    async def list_for_unit(
        self, unit_id: uuid.UUID, status: MaintenanceStatus | None = None
    ) -> list[MaintenanceRequest]:
        return await self._repo.get_for_unit(unit_id, status=status)

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, status: MaintenanceStatus | None = None
    ) -> list[MaintenanceRequest]:
        return await self._repo.get_for_tenant(tenant_id, status=status)

    async def list_all(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        req_status: MaintenanceStatus | None = None,
        priority: MaintenancePriority | None = None,
        category: str | None = None,
    ) -> list[MaintenanceRequest]:
        """Filter-aware listing of all maintenance requests."""
        from app.models.maintenance import MaintenanceCategory
        stmt = (
            select(MaintenanceRequest)
            .options(
                joinedload(MaintenanceRequest.tenant),
                joinedload(MaintenanceRequest.unit).joinedload(Unit.building),
            )
        )
        if req_status:
            stmt = stmt.where(MaintenanceRequest.status == req_status)
        if priority:
            stmt = stmt.where(MaintenanceRequest.priority == priority)
        if category:
            stmt = stmt.where(MaintenanceRequest.category == MaintenanceCategory(category))
        stmt = stmt.offset(skip).limit(limit).order_by(MaintenanceRequest.reported_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_sla_breached(self) -> list[MaintenanceRequest]:
        """Return all open requests that have passed their SLA deadline."""
        return await self._repo.get_open_past_sla()

    async def cancel_request(self, request_id: uuid.UUID, reason: str | None = None) -> MaintenanceRequest:
        req = await self._repo.get_by_id(request_id)
        if not req:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Maintenance request not found.")
        if req.status in (MaintenanceStatus.COMPLETED, MaintenanceStatus.CANCELLED):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Request is already {req.status.value} and cannot be cancelled.",
            )
        update_data: dict = {"status": MaintenanceStatus.CANCELLED}
        if reason:
            update_data["resolution_notes"] = reason
        return await self._repo.update(request_id, update_data)
