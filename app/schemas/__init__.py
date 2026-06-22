"""app/schemas/__init__.py"""

from app.schemas.agent import AgentRequest, AgentResponse
from app.schemas.building import BuildingCreate, BuildingRead, BuildingUpdate, BuildingWithUnits
from app.schemas.lease import LeaseCreate, LeaseDetail, LeaseRead, LeaseUpdate
from app.schemas.maintenance import (
    MaintenanceRequestCreate,
    MaintenanceRequestDetail,
    MaintenanceRequestRead,
    MaintenanceRequestUpdate,
)
from app.schemas.renewal import RenewalCreate, RenewalRead, RenewalUpdate
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate
from app.schemas.unit import UnitCreate, UnitRead, UnitReadWithBuilding, UnitUpdate

__all__ = [
    "BuildingCreate", "BuildingRead", "BuildingUpdate", "BuildingWithUnits",
    "UnitCreate", "UnitRead", "UnitReadWithBuilding", "UnitUpdate",
    "TenantCreate", "TenantRead", "TenantUpdate",
    "LeaseCreate", "LeaseRead", "LeaseDetail", "LeaseUpdate",
    "MaintenanceRequestCreate", "MaintenanceRequestRead",
    "MaintenanceRequestDetail", "MaintenanceRequestUpdate",
    "RenewalCreate", "RenewalRead", "RenewalUpdate",
    "AgentRequest", "AgentResponse",
]
