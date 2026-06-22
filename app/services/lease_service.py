"""
app/services/lease_service.py
------------------------------
Business logic for the lease lifecycle.

Responsibilities
────────────────
• Enforce pre-conditions before writes (unit available, tenant not blacklisted).
• Generate human-readable lease numbers.
• Transition unit status in the same transaction as the lease write.
• Raise HTTPException (409/404/422) so routes stay thin.

Financial operations (rent payments, invoices, deposits) are out of scope.
"""

import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.lease import Lease, LeaseStatus
from app.models.unit import UnitStatus
from app.repositories.lease_repository import LeaseRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.tenant_repository import TenantRepository
from app.schemas.lease import LeaseCreate, LeaseUpdate


def _generate_lease_number() -> str:
    import uuid as _uuid
    suffix = str(_uuid.uuid4().int)[:6].zfill(6)
    return f"LSE-{date.today().year}-{suffix}"


class LeaseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._leases = LeaseRepository(session)
        self._units = UnitRepository(session)
        self._tenants = TenantRepository(session)

    async def create_lease(self, data: LeaseCreate, created_by: str | None = None) -> Lease:
        # Guard: unit must exist and be available
        unit = await self._units.get_by_id(data.unit_id)
        if not unit:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found.")
        if unit.status != UnitStatus.AVAILABLE:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Unit {unit.unit_number} is not available (status: {unit.status.value}).",
            )

        # Guard: tenant must exist and not be blacklisted
        tenant = await self._tenants.get_by_id(data.tenant_id)
        if not tenant:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
        if tenant.is_blacklisted:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Tenant is blacklisted and cannot sign a lease."
            )

        lease = await self._leases.create(
            {
                **data.model_dump(),
                "lease_number": _generate_lease_number(),
                "status": LeaseStatus.DRAFT,
                "created_by": created_by,
            }
        )
        # Reserve the unit so no parallel lease can be created
        await self._units.update_status(data.unit_id, UnitStatus.RESERVED)
        return lease

    async def get_lease(self, lease_id: uuid.UUID) -> Lease:
        lease = await self._leases.get_with_details(lease_id)
        if not lease:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found.")
        return lease

    async def update_lease(self, lease_id: uuid.UUID, data: LeaseUpdate) -> Lease:
        lease = await self._leases.get_by_id(lease_id)
        if not lease:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found.")

        update_data = data.model_dump(exclude_none=True)

        # On activation, mark unit occupied
        if update_data.get("status") == LeaseStatus.ACTIVE:
            await self._units.update_status(lease.unit_id, UnitStatus.OCCUPIED)

        # On termination/expiry, mark unit available
        if update_data.get("status") in (LeaseStatus.TERMINATED, LeaseStatus.EXPIRED):
            await self._units.update_status(lease.unit_id, UnitStatus.AVAILABLE)

        updated = await self._leases.update(lease_id, update_data)
        return updated

    async def get_expiring_leases(self, days_ahead: int = 180) -> list[Lease]:
        return await self._leases.get_expiring_soon(days_ahead)

    async def list_leases(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        lease_status: LeaseStatus | None = None,
        tenant_id: uuid.UUID | None = None,
        unit_id: uuid.UUID | None = None,
    ) -> list[Lease]:
        """Filter-aware lease listing."""
        stmt = (
            select(Lease)
            .options(
                joinedload(Lease.tenant),
                joinedload(Lease.unit).joinedload("building"),
            )
        )
        if lease_status:
            stmt = stmt.where(Lease.status == lease_status)
        if tenant_id:
            stmt = stmt.where(Lease.tenant_id == tenant_id)
        if unit_id:
            stmt = stmt.where(Lease.unit_id == unit_id)
        stmt = stmt.offset(skip).limit(limit).order_by(Lease.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[Lease]:
        tenant = await self._tenants.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
        return await self._leases.get_active_for_tenant(tenant_id)

    async def terminate_lease(self, lease_id: uuid.UUID) -> Lease:
        """Convenience endpoint to set status=terminated and free the unit."""
        from app.schemas.lease import LeaseUpdate
        return await self.update_lease(
            lease_id,
            LeaseUpdate(status=LeaseStatus.TERMINATED),
        )
