import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.maintenance import MaintenanceRequest, MaintenancePriority, MaintenanceStatus
from app.repositories.base import BaseRepository


_PRIORITY_ORDER = {
    MaintenancePriority.EMERGENCY: 1,
    MaintenancePriority.HIGH: 2,
    MaintenancePriority.MEDIUM: 3,
    MaintenancePriority.LOW: 4,
}


class MaintenanceRepository(BaseRepository[MaintenanceRequest]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(MaintenanceRequest, session)

    async def get_by_reference(self, reference_number: str) -> MaintenanceRequest | None:
        result = await self.session.execute(
            select(MaintenanceRequest).where(
                MaintenanceRequest.reference_number == reference_number
            )
        )
        return result.scalar_one_or_none()

    async def get_for_unit(
        self, unit_id: uuid.UUID, *, status: MaintenanceStatus | None = None
    ) -> list[MaintenanceRequest]:
        stmt = select(MaintenanceRequest).where(MaintenanceRequest.unit_id == unit_id)
        if status:
            stmt = stmt.where(MaintenanceRequest.status == status)
        stmt = stmt.order_by(MaintenanceRequest.reported_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_for_tenant(
        self, tenant_id: uuid.UUID, *, status: MaintenanceStatus | None = None
    ) -> list[MaintenanceRequest]:
        stmt = select(MaintenanceRequest).where(
            MaintenanceRequest.tenant_id == tenant_id
        )
        if status:
            stmt = stmt.where(MaintenanceRequest.status == status)
        stmt = stmt.order_by(MaintenanceRequest.reported_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_open_past_sla(self) -> list[MaintenanceRequest]:
        """Return open requests that have breached their SLA deadline."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(MaintenanceRequest).where(
                MaintenanceRequest.status.not_in(
                    [MaintenanceStatus.COMPLETED, MaintenanceStatus.CANCELLED]
                ),
                MaintenanceRequest.sla_due_at <= now,
            )
        )
        return list(result.scalars().all())
