"""
app/services/building_service.py
----------------------------------
Business logic for building portfolio management.

Responsibilities
────────────────
• Filter-aware listing (by area, is_active) — not possible in BaseRepository.
• Deactivation guard: blocks deactivating a building that still has occupied units.
• Unit listing for a building with optional status filter.
• Raises HTTPException so routes remain thin.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.building import Building
from app.models.unit import Unit, UnitStatus
from app.repositories.base import BaseRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.building import BuildingCreate, BuildingUpdate


class BuildingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = BaseRepository(Building, session)
        self._units = UnitRepository(session)

    async def list_buildings(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        area: str | None = None,
        is_active: bool | None = None,
    ) -> list[Building]:
        stmt = select(Building)
        if area:
            stmt = stmt.where(Building.area.ilike(f"%{area}%"))
        if is_active is not None:
            stmt = stmt.where(Building.is_active == is_active)
        stmt = stmt.offset(skip).limit(limit).order_by(Building.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_buildings(
        self, *, area: str | None = None, is_active: bool | None = None
    ) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(Building)
        if area:
            stmt = stmt.where(Building.area.ilike(f"%{area}%"))
        if is_active is not None:
            stmt = stmt.where(Building.is_active == is_active)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_building(self, building_id: uuid.UUID) -> Building:
        building = await self._repo.get_by_id(building_id)
        if not building:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Building not found.")
        return building

    async def get_building_with_units(self, building_id: uuid.UUID) -> Building:
        result = await self._session.execute(
            select(Building)
            .options(selectinload(Building.units))
            .where(Building.id == building_id)
        )
        building = result.scalar_one_or_none()
        if not building:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Building not found.")
        return building

    async def create_building(self, data: BuildingCreate) -> Building:
        return await self._repo.create(data.model_dump())

    async def update_building(self, building_id: uuid.UUID, data: BuildingUpdate) -> Building:
        updated = await self._repo.update(building_id, data.model_dump(exclude_none=True))
        if not updated:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Building not found.")
        return updated

    async def deactivate_building(self, building_id: uuid.UUID) -> Building:
        """
        Soft-delete a building by setting is_active = False.
        Blocked if the building has any occupied units.
        """
        building = await self.get_building(building_id)

        # Guard: cannot deactivate if units are occupied
        occupied_count_result = await self._session.execute(
            select(Unit)
            .where(Unit.building_id == building_id, Unit.status == UnitStatus.OCCUPIED)
            .limit(1)
        )
        if occupied_count_result.scalar_one_or_none():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Building cannot be deactivated while it has occupied units.",
            )

        updated = await self._repo.update(building_id, {"is_active": False})
        return updated

    async def get_units_for_building(
        self, building_id: uuid.UUID, unit_status: UnitStatus | None = None
    ) -> list[Unit]:
        await self.get_building(building_id)  # raises 404 if not found
        units = await self._units.get_by_building(building_id)
        if unit_status:
            units = [u for u in units if u.status == unit_status]
        return units
