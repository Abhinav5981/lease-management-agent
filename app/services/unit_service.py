"""
app/services/unit_service.py
------------------------------
Business logic for unit management.

Responsibilities
────────────────
• Validate parent building exists before creating a unit.
• Prevent deactivation of occupied units.
• Provide enriched single-unit fetch (with building joinedload).
• Raises HTTPException so routes remain thin.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.building import Building
from app.models.unit import Unit, UnitStatus
from app.repositories.base import BaseRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.unit import UnitCreate, UnitUpdate


class UnitService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = UnitRepository(session)
        self._buildings = BaseRepository(Building, session)

    async def list_units(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        area: str | None = None,
        unit_type=None,
        bedrooms: int | None = None,
        unit_status: UnitStatus | None = None,
        available_only: bool = False,
    ) -> list[Unit]:
        """
        Flexible unit listing.
        When available_only or search params are provided, delegates to
        UnitRepository.search_available(); otherwise returns all units.
        """
        if available_only or area or unit_type or bedrooms is not None:
            return await self._repo.search_available(
                area=area,
                unit_type=unit_type,
                bedrooms=bedrooms,
                skip=skip,
                limit=limit,
            )

        stmt = (
            select(Unit)
            .options(joinedload(Unit.building))
            .where(Unit.is_active == True)
        )
        if unit_status:
            stmt = stmt.where(Unit.status == unit_status)
        stmt = stmt.offset(skip).limit(limit).order_by(Unit.unit_number)
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_unit(self, unit_id: uuid.UUID) -> Unit:
        """Return unit with building joinedloaded, or 404."""
        result = await self._session.execute(
            select(Unit)
            .options(joinedload(Unit.building))
            .where(Unit.id == unit_id)
        )
        unit = result.scalar_one_or_none()
        if not unit:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found.")
        return unit

    async def create_unit(self, data: UnitCreate) -> Unit:
        # Validate parent building exists and is active
        building = await self._buildings.get_by_id(data.building_id)
        if not building:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Building not found.")
        if not building.is_active:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Cannot create a unit in an inactive building.",
            )
        unit = await self._repo.create(data.model_dump())
        return unit

    async def update_unit(self, unit_id: uuid.UUID, data: UnitUpdate) -> Unit:
        unit = await self._repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found.")
        updated = await self._repo.update(unit_id, data.model_dump(exclude_none=True))
        return updated

    async def deactivate_unit(self, unit_id: uuid.UUID) -> Unit:
        """
        Soft-delete a unit by setting is_active = False.
        Blocked if the unit is currently occupied.
        """
        unit = await self._repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found.")
        if unit.status == UnitStatus.OCCUPIED:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Cannot deactivate a unit with an active tenancy.",
            )
        return await self._repo.update(unit_id, {"is_active": False})
