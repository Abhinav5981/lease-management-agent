"""
agent/db.py
-----------
asyncpg connection pool — singleton, lazily initialised.

Production notes
────────────────
• Set statement_cache_size=0 when routing through PgBouncer (transaction mode).
• Adjust min_size / max_size to match your deployment (typical: 2–10 per pod).
• Call close_pool() on application shutdown to drain gracefully.
"""

import os
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Return (or lazily create) the shared connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=os.environ["DATABASE_URL"],
            min_size=2,
            max_size=10,
            command_timeout=30,
            # Required when sitting behind PgBouncer in transaction mode
            statement_cache_size=0,
        )
    return _pool


async def close_pool() -> None:
    """Drain and close the pool — call on application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
