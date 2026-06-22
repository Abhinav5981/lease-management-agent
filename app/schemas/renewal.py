import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.renewal import RenewalStatus, TenantRenewalResponse
from app.schemas.common import OrmBase, TimestampSchema


class RenewalCreate(BaseModel):
    lease_id: uuid.UUID
    new_end_date: date
    proposed_rent_aed: Decimal = Field(gt=0)


class RenewalUpdate(BaseModel):
    status: RenewalStatus | None = None
    final_rent_aed: Decimal | None = None
    tenant_counter_offer_aed: Decimal | None = None
    tenant_response: TenantRenewalResponse | None = None
    tenant_responded_at: datetime | None = None
    notice_sent_at: datetime | None = None
    rera_notice_compliant: bool | None = None
    rera_permitted_increase_pct: Decimal | None = None
    rera_max_rent_aed: Decimal | None = None
    rera_index_checked_at: datetime | None = None
    new_lease_id: uuid.UUID | None = None


class RenewalRead(OrmBase, TimestampSchema):
    id: uuid.UUID
    lease_id: uuid.UUID
    tenant_id: uuid.UUID
    unit_id: uuid.UUID
    new_start_date: date
    new_end_date: date
    previous_rent_aed: Decimal
    proposed_rent_aed: Decimal
    rera_permitted_increase_pct: Decimal | None
    rera_max_rent_aed: Decimal | None
    rera_index_checked_at: datetime | None
    final_rent_aed: Decimal | None
    tenant_counter_offer_aed: Decimal | None
    notice_sent_at: datetime | None
    notice_due_by: date
    rera_notice_compliant: bool | None
    tenant_response: TenantRenewalResponse
    tenant_responded_at: datetime | None
    status: RenewalStatus
    new_lease_id: uuid.UUID | None
    created_by: str | None
