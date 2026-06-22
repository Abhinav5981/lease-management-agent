"""
app/repositories/base.py
-------------------------
Generic async CRUD repository.

All entity-specific repositories extend BaseRepository[ModelT] and
inherit get_by_id, get_all, create, update, delete for free.
Domain-specific query methods are added in each subclass.
"""

import uuid
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Generic CRUD repository backed by SQLAlchemy async session.

    Args:
        model:   The ORM model class (e.g. Lease, Tenant).
        session: The async session for the current request, injected by FastAPI.
    """

    def __init__(self, model: type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, id: uuid.UUID) -> ModelT | None:
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, *, skip: int = 0, limit: int = 100) -> list[ModelT]:
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()

    async def create(self, data: dict) -> ModelT:
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()   # assigns DB-generated fields (id, created_at)
        await self.session.refresh(instance)
        return instance

    async def update(self, id: uuid.UUID, data: dict) -> ModelT | None:
        instance = await self.get_by_id(id)
        if not instance:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: uuid.UUID) -> bool:
        instance = await self.get_by_id(id)
        if not instance:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True
