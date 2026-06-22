import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.lease import LeaseStatus
from app.schemas.common import OrmBase, TenantSummary, TimestampSchema, UnitSummary


class LeaseCreate(BaseModel):
    unit_id: uuid.UUID
    tenant_id: uuid.UUID
    start_date: date
    end_date: date
    annual_rent_aed: Decimal = Field(gt=0)
    notice_period_days: int = Field(default=60, ge=1)

    @model_validator(mode="after")
    def end_after_start(self) -> "LeaseCreate":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class LeaseUpdate(BaseModel):
    status: LeaseStatus | None = None
    ejari_number: str | None = None
    ejari_registration_date: date | None = None
    ejari_expiry_date: date | None = None
    signed_by_tenant_at: datetime | None = None
    signed_by_company_at: datetime | None = None
    signing_platform: str | None = None


class LeaseRead(OrmBase, TimestampSchema):
    id: uuid.UUID
    lease_number: str
    unit_id: uuid.UUID
    tenant_id: uuid.UUID
    start_date: date
    end_date: date
    annual_rent_aed: Decimal
    notice_period_days: int
    status: LeaseStatus
    ejari_number: str | None
    ejari_registration_date: date | None
    ejari_expiry_date: date | None
    signed_by_tenant_at: datetime | None
    signed_by_company_at: datetime | None
    signing_platform: str | None
    created_by: str | None


class LeaseDetail(LeaseRead):
    """
    Enriched lease response for GET /leases/{id}.
    Includes nested tenant and unit (with building) loaded via joinedload.
    """

    tenant: TenantSummary | None = None
    unit: UnitSummary | None = None
