"""
app/api/v1/buildings.py
------------------------
CRUD endpoints for buildings.

Routes
───────
GET    /buildings                  — list with filters
POST   /buildings                  — create
GET    /buildings/{id}             — detail with units
PATCH  /buildings/{id}             — partial update
DELETE /buildings/{id}             — soft deactivate (guarded)
GET    /buildings/{id}/units       — units belonging to this building
"""

import uuid

from fastapi import APIRouter, Query, status

from app.dependencies import DBSession
from app.models.unit import UnitStatus
from app.schemas.building import BuildingCreate, BuildingRead, BuildingUpdate, BuildingWithUnits
from app.schemas.common import MessageResponse
from app.schemas.unit import UnitRead
from app.services.building_service import BuildingService

router = APIRouter(prefix="/buildings", tags=["Buildings"])


@router.get("", response_model=list[BuildingRead], summary="List buildings")
async def list_buildings(
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    area: str | None = Query(None, description="Filter by Dubai area, e.g. 'Dubai Marina'."),
    is_active: bool | None = Query(None, description="Filter by active status."),
):
    svc = BuildingService(db)
    return await svc.list_buildings(skip=skip, limit=limit, area=area, is_active=is_active)


@router.post("", response_model=BuildingRead, status_code=status.HTTP_201_CREATED, summary="Create building")
async def create_building(data: BuildingCreate, db: DBSession):
    svc = BuildingService(db)
    return await svc.create_building(data)


@router.get("/{building_id}", response_model=BuildingWithUnits, summary="Get building with units")
async def get_building(building_id: uuid.UUID, db: DBSession):
    """
    Returns the building and its full unit inventory.
    Unit list is loaded via selectinload — no N+1 queries.
    """
    svc = BuildingService(db)
    return await svc.get_building_with_units(building_id)


@router.patch("/{building_id}", response_model=BuildingRead, summary="Update building")
async def update_building(building_id: uuid.UUID, data: BuildingUpdate, db: DBSession):
    svc = BuildingService(db)
    return await svc.update_building(building_id, data)


@router.delete(
    "/{building_id}",
    response_model=MessageResponse,
    summary="Deactivate building",
)
async def deactivate_building(building_id: uuid.UUID, db: DBSession):
    """
    Soft-deletes a building by setting is_active = False.
    Fails with 409 if any unit in the building is currently occupied.
    """
    svc = BuildingService(db)
    await svc.deactivate_building(building_id)
    return MessageResponse(message="Building deactivated successfully.")


@router.get(
    "/{building_id}/units",
    response_model=list[UnitRead],
    summary="List units for a building",
)
async def list_units_for_building(
    building_id: uuid.UUID,
    db: DBSession,
    unit_status: UnitStatus | None = Query(None, description="Filter by unit status."),
):
    svc = BuildingService(db)
    return await svc.get_units_for_building(building_id, unit_status=unit_status)
