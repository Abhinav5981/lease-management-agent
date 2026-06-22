"""
app/main.py
-----------
FastAPI application factory with lifespan management.

Startup:  initialises Qdrant collection.
Shutdown: drains the SQLAlchemy connection pool and Qdrant client.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.v1.router import router as v1_router
from app.db.session import engine
from app.dependencies import get_qdrant


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────
    qdrant = get_qdrant()
    await qdrant.ensure_collection()
    yield
    # ── Shutdown ──────────────────────────────────────────────────────
    await engine.dispose()
    await qdrant.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_TITLE,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # Tighten in production to specific frontend origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router)

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    return app


app = create_app()
