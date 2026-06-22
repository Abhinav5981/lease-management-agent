import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.unit import UnitStatus, UnitType
from app.schemas.common import OrmBase, TimestampSchema


class BuildingCreate(BaseModel):
    name: str = Field(max_length=150)
    name_ar: str | None = Field(None, max_length=150)
    address_line1: str = Field(max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    area: str = Field(max_length=100)
    city: str = Field(default="Dubai", max_length=50)
    makani_number: str | None = Field(None, max_length=20)
    total_floors: int = Field(gt=0)
    total_units: int = Field(gt=0)
    year_built: int | None = None
    is_active: bool = True


class BuildingUpdate(BaseModel):
    name: str | None = Field(None, max_length=150)
    name_ar: str | None = Field(None, max_length=150)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = None
    area: str | None = Field(None, max_length=100)
    makani_number: str | None = None
    total_floors: int | None = Field(None, gt=0)
    total_units: int | None = Field(None, gt=0)
    year_built: int | None = None
    is_active: bool | None = None


class BuildingRead(OrmBase, TimestampSchema):
    id: uuid.UUID
    name: str
    name_ar: str | None
    address_line1: str
    address_line2: str | None
    area: str
    city: str
    makani_number: str | None
    total_floors: int
    total_units: int
    year_built: int | None
    is_active: bool


class UnitBrief(OrmBase):
    """Condensed unit view embedded inside BuildingWithUnits."""

    id: uuid.UUID
    unit_number: str
    floor_number: int
    unit_type: UnitType
    bedrooms: int
    bathrooms: int
    area_sqft: Decimal
    status: UnitStatus


class BuildingWithUnits(BuildingRead):
    """Building detail response including its unit inventory."""

    units: list[UnitBrief] = []
