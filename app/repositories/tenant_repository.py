from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tenant import Tenant
from app.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Tenant, session)

    async def search(self, query: str, *, limit: int = 10) -> list[Tenant]:
        """Full-text search by name, email, phone, or Emirates ID."""
        result = await self.session.execute(
            select(Tenant)
            .where(
                Tenant.is_active == True,
                or_(
                    (Tenant.first_name + " " + Tenant.last_name).ilike(f"%{query}%"),
                    Tenant.first_name.ilike(f"%{query}%"),
                    Tenant.last_name.ilike(f"%{query}%"),
                    Tenant.email == query,
                    Tenant.phone == query,
                    Tenant.emirates_id == query,
                ),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_email(self, email: str) -> Tenant | None:
        result = await self.session.execute(
            select(Tenant).where(Tenant.email == email)
        )
        return result.scalar_one_or_none()

    async def get_expiring_documents(self, days_ahead: int = 30) -> list[Tenant]:
        """Return tenants with any document expiring within `days_ahead` days."""
        from datetime import date, timedelta
        from sqlalchemy import or_
        cutoff = date.today() + timedelta(days=days_ahead)
        result = await self.session.execute(
            select(Tenant).where(
                Tenant.is_active == True,
                or_(
                    Tenant.passport_expiry <= cutoff,
                    Tenant.emirates_id_expiry <= cutoff,
                    Tenant.visa_expiry <= cutoff,
                ),
            )
        )
        return list(result.scalars().all())
