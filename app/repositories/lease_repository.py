import uuid
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.lease import Lease, LeaseStatus
from app.models.unit import Unit
from app.repositories.base import BaseRepository


class LeaseRepository(BaseRepository[Lease]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Lease, session)

    async def get_by_lease_number(self, lease_number: str) -> Lease | None:
        result = await self.session.execute(
            select(Lease).where(Lease.lease_number == lease_number)
        )
        return result.scalar_one_or_none()

    async def get_active_for_unit(self, unit_id: uuid.UUID) -> Lease | None:
        result = await self.session.execute(
            select(Lease).where(
                Lease.unit_id == unit_id,
                Lease.status == LeaseStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_for_tenant(self, tenant_id: uuid.UUID) -> list[Lease]:
        result = await self.session.execute(
            select(Lease).where(
                Lease.tenant_id == tenant_id,
                Lease.status == LeaseStatus.ACTIVE,
            )
        )
        return list(result.scalars().all())

    async def get_expiring_soon(self, days_ahead: int = 180) -> list[Lease]:
        """Return active leases ending within `days_ahead` days."""
        cutoff = date.today() + timedelta(days=days_ahead)
        result = await self.session.execute(
            select(Lease)
            .options(joinedload(Lease.tenant), joinedload(Lease.unit))
            .where(
                Lease.status == LeaseStatus.ACTIVE,
                Lease.end_date <= cutoff,
                Lease.end_date >= date.today(),
            )
            .order_by(Lease.end_date)
        )
        return list(result.scalars().unique().all())

    async def get_with_details(self, lease_id: uuid.UUID) -> Lease | None:
        result = await self.session.execute(
            select(Lease)
            .options(
                joinedload(Lease.tenant),
                joinedload(Lease.unit).joinedload(Unit.building),
            )
            .where(Lease.id == lease_id)
        )
        return result.scalar_one_or_none()
