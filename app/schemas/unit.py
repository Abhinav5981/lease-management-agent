import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.unit import UnitStatus, UnitType
from app.schemas.common import BuildingSummary, TimestampSchema


class UnitCreate(BaseModel):
    building_id: uuid.UUID
    unit_number: str = Field(max_length=20)
    floor_number: int
    unit_type: UnitType
    bedrooms: int = Field(default=0, ge=0)
    bathrooms: int = Field(default=1, ge=0)
    area_sqft: Decimal = Field(gt=0)
    is_active: bool = True


class UnitUpdate(BaseModel):
    unit_type: UnitType | None = None
    bedrooms: int | None = Field(None, ge=0)
    bathrooms: int | None = Field(None, ge=0)
    area_sqft: Decimal | None = Field(None, gt=0)
    status: UnitStatus | None = None
    is_active: bool | None = None


class UnitRead(TimestampSchema):
    id: uuid.UUID
    building_id: uuid.UUID
    unit_number: str
    floor_number: int
    unit_type: UnitType
    bedrooms: int
    bathrooms: int
    area_sqft: Decimal
    status: UnitStatus
    is_active: bool


class UnitReadWithBuilding(UnitRead):
    """Unit detail response with nested building context."""

    building: BuildingSummary | None = None
