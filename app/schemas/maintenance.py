import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.maintenance import MaintenanceCategory, MaintenancePriority, MaintenanceStatus
from app.schemas.common import OrmBase, TenantSummary, TimestampSchema, UnitSummary


class MaintenanceRequestCreate(BaseModel):
    unit_id: uuid.UUID
    tenant_id: uuid.UUID
    category: MaintenanceCategory
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    title: str = Field(max_length=255)
    description: str | None = None


class MaintenanceRequestUpdate(BaseModel):
    status: MaintenanceStatus | None = None
    assigned_to: str | None = None
    assigned_at: datetime | None = None
    completed_at: datetime | None = None
    resolution_notes: str | None = None
    tenant_rating: int | None = Field(None, ge=1, le=5)
    tenant_feedback: str | None = None


class MaintenanceRequestRead(OrmBase, TimestampSchema):
    id: uuid.UUID
    reference_number: str
    unit_id: uuid.UUID
    lease_id: uuid.UUID | None
    tenant_id: uuid.UUID
    category: MaintenanceCategory
    priority: MaintenancePriority
    status: MaintenanceStatus
    title: str
    description: str | None
    assigned_to: str | None
    assigned_at: datetime | None
    sla_due_at: datetime | None
    reported_at: datetime
    completed_at: datetime | None
    resolution_notes: str | None
    tenant_rating: int | None
    tenant_feedback: str | None


class MaintenanceRequestDetail(MaintenanceRequestRead):
    """
    Enriched response for GET /maintenance/{id}.
    Includes nested tenant and unit (with building).
    """

    tenant: TenantSummary | None = None
    unit: UnitSummary | None = None
