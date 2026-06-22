import uuid
from fastapi import APIRouter, status
from app.dependencies import DBSession
from app.services.renewal_service import RenewalService
from app.schemas.renewal import RenewalCreate, RenewalRead, RenewalUpdate

router = APIRouter(prefix="/renewals", tags=["Renewals"])


@router.post("", response_model=RenewalRead, status_code=status.HTTP_201_CREATED)
async def initiate_renewal(data: RenewalCreate, db: DBSession):
    svc = RenewalService(db)
    return await svc.initiate_renewal(data)


@router.get("/{renewal_id}", response_model=RenewalRead)
async def get_renewal(renewal_id: uuid.UUID, db: DBSession):
    svc = RenewalService(db)
    return await svc.get_renewal(renewal_id)


@router.patch("/{renewal_id}", response_model=RenewalRead)
async def update_renewal(renewal_id: uuid.UUID, data: RenewalUpdate, db: DBSession):
    svc = RenewalService(db)
    return await svc.update_renewal(renewal_id, data)


@router.get("/lease/{lease_id}", response_model=list[RenewalRead])
async def renewals_for_lease(lease_id: uuid.UUID, db: DBSession):
    svc = RenewalService(db)
    return await svc.list_for_lease(lease_id)
