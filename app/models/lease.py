"""
app/models/lease.py
--------------------
The core tenancy agreement between a tenant and the company for a specific unit.
annual_rent_aed is a lease term stored for RERA compliance checks — not a
payment instruction.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lease_document import LeaseDocument
    from app.models.maintenance import MaintenanceRequest
    from app.models.renewal import Renewal
    from app.models.tenant import Tenant
    from app.models.unit import Unit


class LeaseStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class Lease(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "leases"
    __table_args__ = (
        # FK joins — most frequent query patterns
        Index("idx_leases_unit_id", "unit_id"),
        Index("idx_leases_tenant_id", "tenant_id"),
        Index("idx_leases_status", "status"),
        # Renewal pipeline: expiring leases (partial — only scan active leases)
        Index(
            "idx_leases_end_date_active",
            "end_date",
            postgresql_where=("status = 'active'"),
        ),
        # Ejari lookup (partial — most leases in draft have no number yet)
        Index(
            "idx_leases_ejari_number",
            "ejari_number",
            postgresql_where=("ejari_number IS NOT NULL"),
        ),
    )

    lease_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)

    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Lease terms ────────────────────────────────────────────────────
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    annual_rent_aed: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notice_period_days: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=60)

    # ── Status ─────────────────────────────────────────────────────────
    status: Mapped[LeaseStatus] = mapped_column(
        Enum(LeaseStatus, name="lease_status_enum", create_type=False),
        nullable=False,
        default=LeaseStatus.DRAFT,
    )

    # ── Ejari (Dubai DLD mandatory registration) ───────────────────────
    ejari_number: Mapped[str | None] = mapped_column(String(50), unique=True)
    ejari_registration_date: Mapped[date | None] = mapped_column(Date)
    ejari_expiry_date: Mapped[date | None] = mapped_column(Date)

    # ── Signing ────────────────────────────────────────────────────────
    signed_by_tenant_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signed_by_company_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signing_platform: Mapped[str | None] = mapped_column(String(50))

    # ── Audit ──────────────────────────────────────────────────────────
    created_by: Mapped[str | None] = mapped_column(String(150))

    # ── Relationships ──────────────────────────────────────────────────
    unit: Mapped["Unit"] = relationship("Unit", back_populates="leases")
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="leases")
    documents: Mapped[list["LeaseDocument"]] = relationship(
        "LeaseDocument", back_populates="lease", foreign_keys="LeaseDocument.lease_id",
        cascade="all, delete-orphan",
    )
    maintenance_requests: Mapped[list["MaintenanceRequest"]] = relationship(
        "MaintenanceRequest", back_populates="lease"
    )
    renewals: Mapped[list["Renewal"]] = relationship(
        "Renewal", back_populates="lease", foreign_keys="Renewal.lease_id"
    )
