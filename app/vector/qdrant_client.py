"""
app/vector/qdrant_client.py
----------------------------
Qdrant vector store integration for the Lease Management Agent.

Purpose
───────
Qdrant stores embeddings of:
  • RERA regulations and Law 26/33 summaries
  • Company lease policies and clause library
  • FAQ / tenant-facing knowledge base
  • Building / unit descriptions (for semantic unit search)

The agent queries this store (via knowledge_search tool) to ground its
answers in verified policy documents rather than LLM memory.

Collection schema
──────────────────
  vector : float[1536]   — text-embedding-3-small output
  payload:
    text      : str       — original chunk text
    source    : str       — document origin (e.g. "rera_law_33", "company_policy")
    doc_type  : str       — "regulation" | "policy" | "faq" | "unit_description"
    metadata  : dict      — arbitrary extra fields (article_number, building_id, etc.)
"""

import asyncio
import uuid
from functools import lru_cache
from typing import Any

from fastembed import TextEmbedding
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    Filter,
    FieldCondition,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import settings


@lru_cache(maxsize=1)
def _get_embedding_model() -> TextEmbedding:
    """Load the fastembed model once; reuse across all requests."""
    return TextEmbedding(model_name=settings.FASTEMBED_MODEL)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using fastembed (runs in thread to stay async-safe)."""
    model = _get_embedding_model()
    loop = asyncio.get_event_loop()
    vectors = await loop.run_in_executor(
        None, lambda: [v.tolist() for v in model.embed(texts)]
    )
    return vectors


class QdrantService:
    """
    Thin async wrapper around qdrant-client with fastembed embeddings.

    All methods are async — they integrate directly with FastAPI's async
    request lifecycle and the LangGraph agent's async tool calls.
    """

    def __init__(self) -> None:
        self._client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
        self._collection = settings.QDRANT_COLLECTION
        self._dim = settings.QDRANT_EMBEDDING_DIM

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def ensure_collection(self) -> None:
        """
        Create the Qdrant collection if it does not already exist.
        Called once on application startup.
        """
        collections = await self._client.get_collections()
        existing = {c.name for c in collections.collections}
        if self._collection not in existing:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=self._dim,
                    distance=Distance.COSINE,
                ),
            )

    async def close(self) -> None:
        await self._client.close()

    # ── Embedding ─────────────────────────────────────────────────────────

    async def embed(self, text: str) -> list[float]:
        """Return a 384-dim embedding vector for the given text."""
        vectors = await embed_texts([text])
        return vectors[0]

    # ── Indexing ──────────────────────────────────────────────────────────

    async def index_document(
        self,
        text: str,
        source: str,
        doc_type: str,
        metadata: dict[str, Any] | None = None,
        point_id: str | None = None,
    ) -> str:
        """
        Embed and index a text chunk into Qdrant.

        Args:
            text:     The text chunk to embed and store.
            source:   Origin identifier (e.g. "rera_law_33", "faq").
            doc_type: High-level category ("regulation" | "policy" | "faq" | "unit_description").
            metadata: Optional dict of extra searchable payload fields.
            point_id: Optional stable UUID. Auto-generated if not provided.

        Returns:
            The Qdrant point ID as a string.
        """
        pid = point_id or str(uuid.uuid4())
        vector = await self.embed(text)
        payload: dict[str, Any] = {
            "text": text,
            "source": source,
            "doc_type": doc_type,
            **(metadata or {}),
        }
        await self._client.upsert(
            collection_name=self._collection,
            points=[PointStruct(id=pid, vector=vector, payload=payload)],
        )
        return pid

    async def index_batch(self, documents: list[dict[str, Any]]) -> list[str]:
        """
        Bulk index a list of document dicts.
        Each dict must have keys: text, source, doc_type.
        Optional keys: metadata, point_id.
        """
        ids: list[str] = []
        for doc in documents:
            pid = await self.index_document(
                text=doc["text"],
                source=doc["source"],
                doc_type=doc["doc_type"],
                metadata=doc.get("metadata"),
                point_id=doc.get("point_id"),
            )
            ids.append(pid)
        return ids

    # ── Retrieval ─────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        doc_type: str | None = None,
        source: str | None = None,
        score_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Semantic search over the knowledge base.

        Args:
            query:           Natural-language query to embed and search.
            top_k:           Maximum number of results to return.
            doc_type:        Optional filter by doc_type payload field.
            source:          Optional filter by source payload field.
            score_threshold: Minimum cosine similarity score (0–1).

        Returns:
            List of dicts with keys: id, score, text, source, doc_type, metadata.
        """
        vector = await self.embed(query)

        # Build optional payload filters
        filter_conditions: list[FieldCondition] = []
        if doc_type:
            filter_conditions.append(
                FieldCondition(key="doc_type", match=MatchValue(value=doc_type))
            )
        if source:
            filter_conditions.append(
                FieldCondition(key="source", match=MatchValue(value=source))
            )

        qdrant_filter = Filter(must=filter_conditions) if filter_conditions else None

        hits = await self._client.search(
            collection_name=self._collection,
            query_vector=vector,
            query_filter=qdrant_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return [
            {
                "id": hit.id,
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "source": hit.payload.get("source", ""),
                "doc_type": hit.payload.get("doc_type", ""),
                "metadata": {
                    k: v
                    for k, v in hit.payload.items()
                    if k not in ("text", "source", "doc_type")
                },
            }
            for hit in hits
        ]

    async def delete_document(self, point_id: str) -> None:
        await self._client.delete(
            collection_name=self._collection,
            points_selector=[point_id],
        )
