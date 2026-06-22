"""
app/models/building.py
-----------------------
Represents a physical building/tower in the portfolio.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.unit import Unit


class Building(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "buildings"
    __table_args__ = (
        # Leasing agents filter by area constantly; partial covers only active buildings
        Index("idx_buildings_area_active", "area", postgresql_where=("is_active = TRUE")),
        Index("idx_buildings_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(150))
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255))
    area: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(50), nullable=False, default="Dubai")
    makani_number: Mapped[str | None] = mapped_column(String(20))
    total_floors: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    total_units: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    year_built: Mapped[int | None] = mapped_column(SmallInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Relationships ──────────────────────────────────────────────────
    units: Mapped[list["Unit"]] = relationship(
        "Unit", back_populates="building", lazy="selectin"
    )
