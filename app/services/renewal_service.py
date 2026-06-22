"""
app/services/renewal_service.py
--------------------------------
Business logic for the RERA-compliant lease renewal lifecycle.

Key rules enforced here:
• Only one open renewal per lease at any time.
• 90-day notice deadline computed and flagged (RERA Law 33).
• proposed_rent_aed must not exceed rera_max_rent_aed when known.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.renewal import Renewal, RenewalStatus
from app.models.lease import LeaseStatus
from app.repositories.renewal_repository import RenewalRepository
from app.repositories.lease_repository import LeaseRepository
from app.schemas.renewal import RenewalCreate, RenewalUpdate


class RenewalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = RenewalRepository(session)
        self._leases = LeaseRepository(session)

    async def initiate_renewal(
        self, data: RenewalCreate, created_by: str | None = None
    ) -> Renewal:
        lease = await self._leases.get_by_id(data.lease_id)
        if not lease:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lease not found.")
        if lease.status != LeaseStatus.ACTIVE:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Only active leases can be renewed (status: {lease.status.value}).",
            )

        # Only one open renewal at a time
        existing = await self._repo.get_open_for_lease(data.lease_id)
        if existing:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"An open renewal already exists for this lease (id: {existing.id}).",
            )

        lease_end: date = lease.end_date
        notice_due_by: date = lease_end - timedelta(days=90)
        rera_notice_compliant: bool = date.today() <= notice_due_by
        new_start: date = lease_end + timedelta(days=1)

        return await self._repo.create(
            {
                "lease_id": data.lease_id,
                "tenant_id": lease.tenant_id,
                "unit_id": lease.unit_id,
                "new_start_date": new_start,
                "new_end_date": data.new_end_date,
                "previous_rent_aed": lease.annual_rent_aed,
                "proposed_rent_aed": data.proposed_rent_aed,
                "notice_due_by": notice_due_by,
                "rera_notice_compliant": rera_notice_compliant,
                "status": RenewalStatus.OFFERED,
                "created_by": created_by,
            }
        )

    async def get_renewal(self, renewal_id: uuid.UUID) -> Renewal:
        renewal = await self._repo.get_by_id(renewal_id)
        if not renewal:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Renewal not found.")
        return renewal

    async def update_renewal(self, renewal_id: uuid.UUID, data: RenewalUpdate) -> Renewal:
        renewal = await self._repo.get_by_id(renewal_id)
        if not renewal:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Renewal not found.")

        update_data = data.model_dump(exclude_none=True)

        # Enforce RERA ceiling if known
        new_rent = update_data.get("final_rent_aed") or update_data.get("proposed_rent_aed")
        if new_rent and renewal.rera_max_rent_aed:
            if Decimal(str(new_rent)) > renewal.rera_max_rent_aed:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Proposed rent AED {new_rent} exceeds RERA maximum "
                    f"AED {renewal.rera_max_rent_aed}.",
                )

        updated = await self._repo.update(renewal_id, update_data)
        return updated

    async def list_for_lease(self, lease_id: uuid.UUID) -> list[Renewal]:
        result = await self._repo.get_for_tenant(lease_id)  # fallback — filter by lease_id
        # Simpler direct query via base repo
        from sqlalchemy import select
        from app.models.renewal import Renewal as RenewalModel
        res = await self._session.execute(
            select(RenewalModel).where(RenewalModel.lease_id == lease_id)
        )
        return list(res.scalars().all())
