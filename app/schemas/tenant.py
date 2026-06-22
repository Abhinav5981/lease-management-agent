import uuid
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field, computed_field
from app.schemas.common import TimestampSchema


class TenantCreate(BaseModel):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    email: EmailStr
    phone: str = Field(max_length=20)
    nationality: str | None = Field(None, max_length=100)
    date_of_birth: date | None = None
    passport_number: str | None = Field(None, max_length=30)
    passport_expiry: date | None = None
    emirates_id: str | None = Field(None, max_length=20)
    emirates_id_expiry: date | None = None
    visa_number: str | None = Field(None, max_length=30)
    visa_expiry: date | None = None
    visa_type: str | None = Field(None, max_length=50)
    employer_name: str | None = Field(None, max_length=150)
    monthly_income_aed: Decimal | None = Field(None, gt=0)


class TenantUpdate(BaseModel):
    phone: str | None = Field(None, max_length=20)
    nationality: str | None = None
    passport_number: str | None = None
    passport_expiry: date | None = None
    emirates_id: str | None = None
    emirates_id_expiry: date | None = None
    visa_number: str | None = None
    visa_expiry: date | None = None
    visa_type: str | None = None
    employer_name: str | None = None
    monthly_income_aed: Decimal | None = None
    is_active: bool | None = None
    is_blacklisted: bool | None = None
    blacklist_reason: str | None = None


class TenantRead(TimestampSchema):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    phone: str
    nationality: str | None
    date_of_birth: date | None
    passport_number: str | None
    passport_expiry: date | None
    emirates_id: str | None
    emirates_id_expiry: date | None
    visa_expiry: date | None
    visa_type: str | None
    employer_name: str | None
    is_active: bool
    is_blacklisted: bool

    @computed_field
    @property
    def full_name(self) -> str:
        """Serialised by Pydantic v2 as a regular response field."""
        return f"{self.first_name} {self.last_name}"
