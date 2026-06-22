"""
app/models/maintenance.py
--------------------------
Tenant-raised maintenance and repair requests with SLA tracking.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lease import Lease
    from app.models.tenant import Tenant
    from app.models.unit import Unit


class MaintenanceCategory(str, enum.Enum):
    HVAC = "hvac"
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    CARPENTRY = "carpentry"
    PAINTING = "painting"
    APPLIANCES = "appliances"
    PEST_CONTROL = "pest_control"
    CLEANING = "cleaning"
    GENERAL = "general"


class MaintenancePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class MaintenanceStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING_TENANT_CONFIRMATION = "pending_tenant_confirmation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MaintenanceRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "maintenance_requests"
    __table_args__ = (
        # FK joins
        Index("idx_maint_unit_id", "unit_id"),
        Index("idx_maint_tenant_id", "tenant_id"),
        Index("idx_maint_lease_id", "lease_id"),
        # Dashboard: open requests ordered by priority
        Index("idx_maint_status", "status"),
        # SLA breach scan: only open/assigned/in-progress requests need sla_due_at checked
        Index(
            "idx_maint_sla_open",
            "sla_due_at", "priority",
            postgresql_where=(
                "status NOT IN ('completed', 'cancelled')"
            ),
        ),
    )

    reference_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)

    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lease_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="SET NULL"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # ── Request details ────────────────────────────────────────────────
    category: Mapped[MaintenanceCategory] = mapped_column(
        Enum(MaintenanceCategory, name="maintenance_category_enum", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    priority: Mapped[MaintenancePriority] = mapped_column(
        Enum(MaintenancePriority, name="maintenance_priority_enum", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MaintenancePriority.MEDIUM,
    )
    status: Mapped[MaintenanceStatus] = mapped_column(
        Enum(MaintenanceStatus, name="maintenance_status_enum", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=MaintenanceStatus.OPEN,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # ── Assignment ─────────────────────────────────────────────────────
    assigned_to: Mapped[str | None] = mapped_column(String(150))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Resolution ─────────────────────────────────────────────────────
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[str | None] = mapped_column(Text)

    # ── Tenant feedback ────────────────────────────────────────────────
    tenant_rating: Mapped[int | None] = mapped_column(SmallInteger)
    tenant_feedback: Mapped[str | None] = mapped_column(Text)
    rated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Relationships ──────────────────────────────────────────────────
    unit: Mapped["Unit"] = relationship("Unit", back_populates="maintenance_requests")
    lease: Mapped["Lease | None"] = relationship("Lease", back_populates="maintenance_requests")
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="maintenance_requests")
