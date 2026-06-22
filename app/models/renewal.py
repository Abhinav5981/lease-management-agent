"""
app/models/renewal.py
----------------------
Tracks the RERA-compliant renewal negotiation for an expiring lease.
Enforces the 90-day notice rule (RERA Law 33) and rental index caps.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lease import Lease
    from app.models.tenant import Tenant
    from app.models.unit import Unit


class RenewalStatus(str, enum.Enum):
    PENDING = "pending"
    OFFERED = "offered"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    LAPSED = "lapsed"


class TenantRenewalResponse(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COUNTER_OFFERED = "counter_offered"


class Renewal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "renewals"
    __table_args__ = (
        # FK joins
        Index("idx_renewals_lease_id", "lease_id"),
        Index("idx_renewals_tenant_id", "tenant_id"),
        Index("idx_renewals_status", "status"),
        # 90-day notice compliance scan: only open renewals where notice not yet sent
        Index(
            "idx_renewals_notice_due",
            "notice_due_by",
            postgresql_where=(
                "status IN ('pending', 'offered') AND notice_sent_at IS NULL"
            ),
        ),
    )

    lease_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Renewal terms ──────────────────────────────────────────────────
    new_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    new_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    previous_rent_aed: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    proposed_rent_aed: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # ── RERA compliance ────────────────────────────────────────────────
    rera_permitted_increase_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    rera_max_rent_aed: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    rera_index_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Negotiation ────────────────────────────────────────────────────
    final_rent_aed: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    tenant_counter_offer_aed: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # ── RERA 90-day notice (Law 33) ────────────────────────────────────
    notice_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notice_due_by: Mapped[date] = mapped_column(Date, nullable=False)
    rera_notice_compliant: Mapped[bool | None] = mapped_column(Boolean)

    # ── Tenant response ────────────────────────────────────────────────
    tenant_response: Mapped[TenantRenewalResponse] = mapped_column(
        Enum(TenantRenewalResponse, name="tenant_renewal_response_enum", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TenantRenewalResponse.PENDING,
    )
    tenant_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Overall status ─────────────────────────────────────────────────
    status: Mapped[RenewalStatus] = mapped_column(
        Enum(RenewalStatus, name="renewal_status_enum", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=RenewalStatus.PENDING,
    )

    # ── Link to new lease after acceptance ─────────────────────────────
    new_lease_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="SET NULL"),
    )

    # ── Audit ──────────────────────────────────────────────────────────
    created_by: Mapped[str | None] = mapped_column(String(150))

    # ── Relationships ──────────────────────────────────────────────────
    lease: Mapped["Lease"] = relationship(
        "Lease", back_populates="renewals", foreign_keys=[lease_id]
    )
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="renewals")
    unit: Mapped["Unit"] = relationship("Unit", back_populates="renewals")
    new_lease: Mapped["Lease | None"] = relationship(
        "Lease", foreign_keys=[new_lease_id]
    )
