"""
app/api/v1/units.py
--------------------
CRUD endpoints for units.

Routes
───────
GET    /units             — list with filters (area, type, bedrooms, status, available_only)
POST   /units             — create (validates parent building)
GET    /units/{id}        — detail with building context
PATCH  /units/{id}        — partial update
DELETE /units/{id}        — soft deactivate (guarded: not occupied)
"""

import uuid

from fastapi import APIRouter, Query, status

from app.dependencies import DBSession
from app.models.unit import UnitStatus, UnitType
from app.schemas.common import MessageResponse
from app.schemas.unit import UnitCreate, UnitRead, UnitReadWithBuilding, UnitUpdate
from app.services.unit_service import UnitService

router = APIRouter(prefix="/units", tags=["Units"])


@router.get("", response_model=list[UnitReadWithBuilding], summary="List units")
async def list_units(
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    area: str | None = Query(None, description="Filter by Dubai area."),
    unit_type: UnitType | None = Query(None),
    bedrooms: int | None = Query(None, ge=0),
    unit_status: UnitStatus | None = Query(None, alias="status"),
    available_only: bool = Query(False, description="Return only available units."),
):
    svc = UnitService(db)
    return await svc.list_units(
        skip=skip,
        limit=limit,
        area=area,
        unit_type=unit_type,
        bedrooms=bedrooms,
        unit_status=unit_status,
        available_only=available_only,
    )


@router.post("", response_model=UnitRead, status_code=status.HTTP_201_CREATED, summary="Create unit")
async def create_unit(data: UnitCreate, db: DBSession):
    """Creates a unit. Validates that the parent building exists and is active."""
    svc = UnitService(db)
    return await svc.create_unit(data)


@router.get("/{unit_id}", response_model=UnitReadWithBuilding, summary="Get unit")
async def get_unit(unit_id: uuid.UUID, db: DBSession):
    """Returns unit detail with nested building summary."""
    svc = UnitService(db)
    return await svc.get_unit(unit_id)


@router.patch("/{unit_id}", response_model=UnitRead, summary="Update unit")
async def update_unit(unit_id: uuid.UUID, data: UnitUpdate, db: DBSession):
    svc = UnitService(db)
    return await svc.update_unit(unit_id, data)


@router.delete(
    "/{unit_id}",
    response_model=MessageResponse,
    summary="Deactivate unit",
)
async def deactivate_unit(unit_id: uuid.UUID, db: DBSession):
    """
    Soft-deletes a unit by setting is_active = False.
    Fails with 409 if the unit is currently occupied.
    """
    svc = UnitService(db)
    await svc.deactivate_unit(unit_id)
    return MessageResponse(message="Unit deactivated successfully.")
