"""
app/models/tenant.py
---------------------
Personal and KYC identity details of a prospective or active tenant.
No financial transaction data (payments, deposits) is stored here.
"""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lease import Lease
    from app.models.lease_document import LeaseDocument
    from app.models.maintenance import MaintenanceRequest
    from app.models.renewal import Renewal


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"
    __table_args__ = (
        # Agent cron: scan only tenants who have a document set (partial — skips NULLs)
        Index(
            "idx_tenants_passport_expiry",
            "passport_expiry",
            postgresql_where=("passport_expiry IS NOT NULL"),
        ),
        Index(
            "idx_tenants_eid_expiry",
            "emirates_id_expiry",
            postgresql_where=("emirates_id_expiry IS NOT NULL"),
        ),
        Index(
            "idx_tenants_visa_expiry",
            "visa_expiry",
            postgresql_where=("visa_expiry IS NOT NULL"),
        ),
    )

    # ── Personal details ───────────────────────────────────────────────
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    nationality: Mapped[str | None] = mapped_column(String(100))
    date_of_birth: Mapped[date | None] = mapped_column(Date)

    # ── Identity documents ─────────────────────────────────────────────
    passport_number: Mapped[str | None] = mapped_column(String(30), unique=True)
    passport_expiry: Mapped[date | None] = mapped_column(Date)
    emirates_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    emirates_id_expiry: Mapped[date | None] = mapped_column(Date)
    visa_number: Mapped[str | None] = mapped_column(String(30))
    visa_expiry: Mapped[date | None] = mapped_column(Date)
    visa_type: Mapped[str | None] = mapped_column(String(50))

    # ── KYC screening (not financial processing) ───────────────────────
    employer_name: Mapped[str | None] = mapped_column(String(150))
    monthly_income_aed: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # ── Lifecycle ─────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blacklist_reason: Mapped[str | None] = mapped_column(Text)

    # ── Relationships ──────────────────────────────────────────────────
    leases: Mapped[list["Lease"]] = relationship("Lease", back_populates="tenant")
    documents: Mapped[list["LeaseDocument"]] = relationship(
        "LeaseDocument", back_populates="tenant", foreign_keys="LeaseDocument.tenant_id",
    )
    maintenance_requests: Mapped[list["MaintenanceRequest"]] = relationship(
        "MaintenanceRequest", back_populates="tenant"
    )
    renewals: Mapped[list["Renewal"]] = relationship("Renewal", back_populates="tenant")
