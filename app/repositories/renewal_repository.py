import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.renewal import Renewal, RenewalStatus
from app.repositories.base import BaseRepository


class RenewalRepository(BaseRepository[Renewal]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Renewal, session)

    async def get_open_for_lease(self, lease_id: uuid.UUID) -> Renewal | None:
        """Return any in-flight renewal for the given lease."""
        result = await self.session.execute(
            select(Renewal).where(
                Renewal.lease_id == lease_id,
                Renewal.status.in_(
                    [RenewalStatus.PENDING, RenewalStatus.OFFERED, RenewalStatus.NEGOTIATING]
                ),
            )
        )
        return result.scalar_one_or_none()

    async def get_for_tenant(self, tenant_id: uuid.UUID) -> list[Renewal]:
        result = await self.session.execute(
            select(Renewal)
            .where(Renewal.tenant_id == tenant_id)
            .order_by(Renewal.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_pending_notices(self) -> list[Renewal]:
        """Return renewals where the 90-day notice has not yet been sent."""
        result = await self.session.execute(
            select(Renewal).where(
                Renewal.status.in_([RenewalStatus.PENDING, RenewalStatus.OFFERED]),
                Renewal.notice_sent_at.is_(None),
            )
        )
        return list(result.scalars().all())
