"""
app/models/unit.py
-------------------
A leasable unit within a building.
"""

import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.lease import Lease
    from app.models.maintenance import MaintenanceRequest
    from app.models.renewal import Renewal


class UnitType(str, enum.Enum):
    STUDIO = "studio"
    ONE_BR = "1br"
    TWO_BR = "2br"
    THREE_BR = "3br"
    FOUR_BR = "4br"
    PENTHOUSE = "penthouse"
    COMMERCIAL = "commercial"
    RETAIL = "retail"


class UnitStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    OCCUPIED = "occupied"
    UNDER_MAINTENANCE = "under_maintenance"


class Unit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("building_id", "unit_number", name="uq_unit_per_building"),
        # FK join — every lease/maintenance query filters by building_id
        Index("idx_units_building_id", "building_id"),
        # Dashboard: units by status
        Index("idx_units_status", "status"),
        # Leasing search: available units by type/bedrooms (partial — skip non-available rows)
        Index(
            "idx_units_available_type_beds",
            "unit_type", "bedrooms",
            postgresql_where=("status = 'available'"),
        ),
    )

    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    unit_number: Mapped[str] = mapped_column(String(20), nullable=False)
    floor_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    unit_type: Mapped[UnitType] = mapped_column(
        Enum(UnitType, name="unit_type_enum", create_type=False, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    bedrooms: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    bathrooms: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    area_sqft: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    status: Mapped[UnitStatus] = mapped_column(
        Enum(UnitStatus, name="unit_status_enum", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UnitStatus.AVAILABLE,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Relationships ──────────────────────────────────────────────────
    building: Mapped["Building"] = relationship("Building", back_populates="units")
    leases: Mapped[list["Lease"]] = relationship("Lease", back_populates="unit")
    maintenance_requests: Mapped[list["MaintenanceRequest"]] = relationship(
        "MaintenanceRequest", back_populates="unit"
    )
    renewals: Mapped[list["Renewal"]] = relationship("Renewal", back_populates="unit")
