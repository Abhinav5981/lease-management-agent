"""app/api/v1/router.py — aggregates all v1 routers under /api/v1"""

from fastapi import APIRouter

from app.api.v1 import buildings, units, tenants, leases, maintenance, renewals, agent

router = APIRouter(prefix="/api/v1")

router.include_router(buildings.router)
router.include_router(units.router)
router.include_router(tenants.router)
router.include_router(leases.router)
router.include_router(maintenance.router)
router.include_router(renewals.router)
router.include_router(agent.router)
