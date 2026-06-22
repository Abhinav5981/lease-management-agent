"""
app/rag/pipeline.py
--------------------
Ingestion pipeline for the Lease Manager Agent RAG system.

Stages
──────
  1. TextChunker       — splits long documents into overlapping chunks so
                         each vector represents a focused, retrievable idea.
  2. IngestionPipeline — orchestrates: chunk → batch embed → batch upsert.

Why chunking matters
─────────────────────
  A 2,000-word policy document embedded as a single vector gets diluted —
  the embedding averages over all topics, reducing retrieval precision.
  Chunks of 600–800 characters each represent a single coherent idea and
  retrieve with much higher relevance scores.

Why batch embedding matters
────────────────────────────
  The previous seed_knowledge.py called embed() once per document (N API
  calls). The OpenAI embeddings endpoint accepts up to 2,048 inputs per
  call. Batching all chunks into groups of 100 reduces API calls by ~100×
  for a typical knowledge base.
"""

import hashlib
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import PointStruct

from app.config import settings
from app.rag.documents import ALL_DOCUMENTS, SOURCE_LABELS
from app.vector.qdrant_client import embed_texts


# ══════════════════════════════════════════════════════════════════════════════
# TEXT CHUNKER
# ══════════════════════════════════════════════════════════════════════════════

class TextChunker:
    """
    Split a document's text into overlapping chunks.

    Strategy:
    1. Split on double newlines (paragraph boundaries) to keep related
       sentences together wherever possible.
    2. If a paragraph exceeds chunk_size, further split on single newlines.
    3. Accumulate paragraphs until the chunk would exceed chunk_size, then
       start a new chunk — carrying the last `overlap` characters forward
       so context is not lost at chunk boundaries.

    Args:
        chunk_size:  Maximum characters per chunk (default 800).
        overlap:     Characters to carry forward into the next chunk (default 120).
    """

    def __init__(self, chunk_size: int = 800, overlap: int = 120) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str, title: str = "") -> list[str]:
        """
        Split text into chunks.

        Each chunk is prefixed with the document title so the embedding
        captures "what document is this about" — critical for disambiguation
        when multiple sources discuss overlapping topics.

        Returns:
            List of chunk strings, each prefixed with "Title: {title}\\n\\n".
        """
        paragraphs = self._split_to_paragraphs(text)
        raw_chunks = self._accumulate(paragraphs)
        prefix = f"Title: {title}\n\n" if title else ""
        return [f"{prefix}{chunk}" for chunk in raw_chunks]

    def _split_to_paragraphs(self, text: str) -> list[str]:
        """Split on double newlines; further split long paragraphs on single newlines."""
        paragraphs: list[str] = []
        for block in text.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            if len(block) <= self.chunk_size:
                paragraphs.append(block)
            else:
                # Long block — split on single newlines
                for line in block.split("\n"):
                    line = line.strip()
                    if line:
                        paragraphs.append(line)
        return paragraphs

    def _accumulate(self, paragraphs: list[str]) -> list[str]:
        """Accumulate paragraphs into chunks, carrying overlap forward."""
        chunks: list[str] = []
        current: list[str] = []
        current_len: int = 0

        for para in paragraphs:
            # If adding this paragraph would exceed chunk_size, flush current chunk
            addition = len(para) + (1 if current else 0)  # +1 for the joining newline
            if current and current_len + addition > self.chunk_size:
                chunk_text = "\n".join(current)
                chunks.append(chunk_text)
                # Carry tail of the last paragraph(s) as overlap
                tail = chunk_text[-self.overlap:] if self.overlap else ""
                current = [tail, para] if tail else [para]
                current_len = len(tail) + len(para) + (1 if tail else 0)
            else:
                current.append(para)
                current_len += addition

        if current:
            chunks.append("\n".join(current))

        return [c for c in chunks if c.strip()]


# ══════════════════════════════════════════════════════════════════════════════
# INGESTION PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

class IngestionPipeline:
    """
    Orchestrates the full ingestion flow:
      documents → chunks → embeddings (batch) → Qdrant upsert (batch)

    Usage:
        pipeline = IngestionPipeline()
        stats = await pipeline.ingest(ALL_DOCUMENTS)

    Args:
        chunk_size:   Max characters per chunk (passed to TextChunker).
        overlap:      Overlap characters between chunks (passed to TextChunker).
        embed_batch:  Max texts per OpenAI embeddings API call (max 2048).
        upsert_batch: Max points per Qdrant upsert call.
    """

    def __init__(
        self,
        chunk_size: int = 800,
        overlap: int = 120,
        embed_batch: int = 100,
        upsert_batch: int = 100,
    ) -> None:
        self._chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
        self._embed_batch = embed_batch
        self._upsert_batch = upsert_batch
        self._qdrant = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
        self._collection = settings.QDRANT_COLLECTION

    # ── Public entry point ────────────────────────────────────────────────────

    async def ingest(
        self,
        documents: list[dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        """
        Run the full ingestion pipeline.

        Args:
            documents: List of document dicts (defaults to ALL_DOCUMENTS if None).

        Returns:
            Stats dict: {"documents": N, "chunks": N, "upserted": N, "skipped": N}
        """
        docs = documents if documents is not None else ALL_DOCUMENTS
        print(f"[Ingestion] Starting. {len(docs)} documents.")

        # Stage 1: Chunk all documents
        all_chunks = self._chunk_all(docs)
        print(f"[Ingestion] Chunked into {len(all_chunks)} chunks.")

        # Stage 2: Batch embed
        texts = [c["text"] for c in all_chunks]
        vectors = await self._embed_all(texts)
        print(f"[Ingestion] Embedded {len(vectors)} chunks.")

        # Stage 3: Build PointStructs
        points = self._build_points(all_chunks, vectors)

        # Stage 4: Batch upsert
        upserted = await self._upsert_all(points)
        print(f"[Ingestion] Upserted {upserted} points to Qdrant.")

        return {
            "documents": len(docs),
            "chunks": len(all_chunks),
            "upserted": upserted,
        }

    async def close(self) -> None:
        await self._qdrant.close()

    # ── Stage 1: Chunking ─────────────────────────────────────────────────────

    def _chunk_all(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Chunk all documents.

        Each output dict has:
          text, source, doc_type, title, point_id (stable), metadata
        """
        result: list[dict[str, Any]] = []
        for doc in documents:
            title = doc.get("title", "")
            source = doc["source"]
            doc_type = doc["doc_type"]
            metadata = doc.get("metadata", {})
            raw_text = doc["text"]

            chunks = self._chunker.chunk(raw_text, title=title)

            for idx, chunk_text in enumerate(chunks):
                # Stable point_id: deterministic hash of (source + title + chunk_index)
                # so re-ingestion upserts rather than duplicates.
                stable_key = f"{source}::{title}::{idx}"
                point_id = str(
                    uuid.UUID(hashlib.md5(stable_key.encode()).hexdigest())
                )
                result.append({
                    "text": chunk_text,
                    "source": source,
                    "doc_type": doc_type,
                    "title": title,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "point_id": point_id,
                    "metadata": {
                        **metadata,
                        "title": title,
                        "chunk_index": idx,
                        "total_chunks": len(chunks),
                        "source_label": SOURCE_LABELS.get(source, source),
                    },
                })
        return result

    # ── Stage 2: Batch embedding ──────────────────────────────────────────────

    async def _embed_all(self, texts: list[str]) -> list[list[float]]:
        """
        Embed all texts using fastembed (local, no API key required).
        Splits into batches to keep memory usage bounded.
        """
        all_vectors: list[list[float]] = []
        for start in range(0, len(texts), self._embed_batch):
            batch = texts[start : start + self._embed_batch]
            batch_vectors = await embed_texts(batch)
            all_vectors.extend(batch_vectors)
            print(f"[Ingestion]   Embedded batch {start}–{start + len(batch) - 1}")
        return all_vectors

    # ── Stage 3: Build Qdrant points ─────────────────────────────────────────

    @staticmethod
    def _build_points(
        chunks: list[dict[str, Any]],
        vectors: list[list[float]],
    ) -> list[PointStruct]:
        points: list[PointStruct] = []
        for chunk, vector in zip(chunks, vectors):
            payload: dict[str, Any] = {
                "text": chunk["text"],
                "source": chunk["source"],
                "doc_type": chunk["doc_type"],
                **chunk["metadata"],
            }
            points.append(
                PointStruct(
                    id=chunk["point_id"],
                    vector=vector,
                    payload=payload,
                )
            )
        return points

    # ── Stage 4: Batch upsert ─────────────────────────────────────────────────

    async def _upsert_all(self, points: list[PointStruct]) -> int:
        """Upsert all points to Qdrant in batches."""
        total = 0
        for start in range(0, len(points), self._upsert_batch):
            batch = points[start : start + self._upsert_batch]
            await self._qdrant.upsert(
                collection_name=self._collection,
                points=batch,
            )
            total += len(batch)
            print(f"[Ingestion]   Upserted batch {start}–{start + len(batch) - 1}")
        return total
