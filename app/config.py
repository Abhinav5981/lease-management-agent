"""
app/config.py
-------------
Centralised application settings via pydantic-settings.

All values are read from environment variables (or a .env file).
Access settings anywhere with: from app.config import settings
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ───────────────────────────────────────────────────────
    APP_TITLE: str = "Lease Management Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── PostgreSQL (asyncpg driver) ────────────────────────────────────────
    # Format: postgresql+asyncpg://user:password@host:5432/dbname
    DATABASE_URL: str

    # ── Groq (free LLM API) ───────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ── Embeddings: fastembed (local, no API key) ─────────────────────────
    FASTEMBED_MODEL: str = "BAAI/bge-small-en-v1.5"

    # ── Qdrant ────────────────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "lease_knowledge"
    QDRANT_EMBEDDING_DIM: int = 384  # bge-small-en-v1.5 output dim

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
