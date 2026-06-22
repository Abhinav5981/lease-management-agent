"""
app/dependencies.py
-------------------
FastAPI dependency functions injected into route handlers.

Usage in a route:
    @router.get("/units")
    async def list_units(db: DBSession, qdrant: QdrantDep): ...
"""

from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.vector.qdrant_client import QdrantService

# ── Database session ───────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a SQLAlchemy async session per request.
    Commits on success, rolls back on any exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DBSession = Annotated[AsyncSession, Depends(get_db)]

# ── Qdrant client ──────────────────────────────────────────────────────────

_qdrant_service: QdrantService | None = None


def get_qdrant() -> QdrantService:
    """Return the shared QdrantService singleton (lazily created)."""
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service


QdrantDep = Annotated[QdrantService, Depends(get_qdrant)]
