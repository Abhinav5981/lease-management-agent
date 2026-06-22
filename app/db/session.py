"""
app/db/session.py
-----------------
Async SQLAlchemy engine and session factory.

Production notes:
• pool_pre_ping=True — validates connections before use (handles stale TCP).
• expire_on_commit=False — avoids lazy-load errors after session.commit().
• autoflush=False — gives explicit control over when SQL is emitted.
• For PgBouncer in transaction mode, add:
    connect_args={"server_settings": {"jit": "off"}}
    and set pool_size to match PgBouncer's pool.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
