"""
app/schemas/common.py
----------------------
Shared Pydantic types and response envelope used across all schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrmBase(BaseModel):
    """Base for all schemas that are serialised from ORM models."""

    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(OrmBase):
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel):
    """Generic wrapper for paginated list endpoints."""

    total: int
    skip: int
    limit: int
    items: list  # Override in typed subclasses


class MessageResponse(BaseModel):
    message: str


class IDResponse(BaseModel):
    id: uuid.UUID


# ---------------------------------------------------------------------------
# Cross-domain summary schemas
# Defined here to avoid circular imports between schema files.
# Importing enums directly from models (not from other schema files).
# ---------------------------------------------------------------------------

from decimal import Decimal  # noqa: E402 — intentional late import

from app.models.unit import UnitStatus, UnitType  # noqa: E402


class BuildingSummary(OrmBase):
    """Minimal building info embedded in unit / lease detail responses."""

    id: uuid.UUID
    name: str
    area: str
    city: str


class TenantSummary(OrmBase):
    """Minimal tenant info embedded in lease / maintenance detail responses."""

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    phone: str
    emirates_id: str | None = None


class UnitSummary(OrmBase):
    """Minimal unit info embedded in lease / maintenance detail responses."""

    id: uuid.UUID
    unit_number: str
    floor_number: int
    unit_type: UnitType
    bedrooms: int
    area_sqft: Decimal
    status: UnitStatus
    building: BuildingSummary | None = None
