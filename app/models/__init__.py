"""
app/models/__init__.py
----------------------
Re-exports all ORM models so Alembic's env.py can import Base and discover
every table with a single:  from app.models import Base
"""

from app.db.base import Base  # noqa: F401 — Base must be imported before models

from app.models.building import Building
from app.models.lease import Lease, LeaseStatus
from app.models.lease_document import DocumentStatus, DocumentType, LeaseDocument
from app.models.maintenance import (
    MaintenanceCategory,
    MaintenancePriority,
    MaintenanceRequest,
    MaintenanceStatus,
)
from app.models.renewal import Renewal, RenewalStatus, TenantRenewalResponse
from app.models.tenant import Tenant
from app.models.unit import Unit, UnitStatus, UnitType

__all__ = [
    "Base",
    "Building",
    "Unit",
    "UnitType",
    "UnitStatus",
    "Tenant",
    "Lease",
    "LeaseStatus",
    "LeaseDocument",
    "DocumentType",
    "DocumentStatus",
    "MaintenanceRequest",
    "MaintenanceCategory",
    "MaintenancePriority",
    "MaintenanceStatus",
    "Renewal",
    "RenewalStatus",
    "TenantRenewalResponse",
]
