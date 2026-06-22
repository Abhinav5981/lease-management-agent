import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.unit import Unit, UnitStatus, UnitType
from app.repositories.base import BaseRepository


class UnitRepository(BaseRepository[Unit]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Unit, session)

    async def search_available(
        self,
        *,
        area: str | None = None,
        unit_type: UnitType | None = None,
        bedrooms: int | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Unit]:
        from sqlalchemy.orm import joinedload
        stmt = (
            select(Unit)
            .options(joinedload(Unit.building))
            .where(Unit.status == UnitStatus.AVAILABLE, Unit.is_active == True)
        )
        if unit_type:
            stmt = stmt.where(Unit.unit_type == unit_type)
        if bedrooms is not None:
            stmt = stmt.where(Unit.bedrooms == bedrooms)
        if area:
            from app.models.building import Building
            stmt = stmt.join(Unit.building).where(
                Building.area.ilike(f"%{area}%")
            )
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_by_building(self, building_id: uuid.UUID) -> list[Unit]:
        result = await self.session.execute(
            select(Unit).where(Unit.building_id == building_id)
        )
        return list(result.scalars().all())

    async def update_status(self, unit_id: uuid.UUID, status: UnitStatus) -> Unit | None:
        return await self.update(unit_id, {"status": status})
