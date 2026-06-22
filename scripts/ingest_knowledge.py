"""
scripts/ingest_knowledge.py
----------------------------
CLI entry point for the RAG ingestion pipeline.

Chunks all documents in app/rag/documents.py, batch-embeds them via
OpenAI, and upserts to Qdrant. Safe to re-run — stable point IDs mean
Qdrant upserts (no duplicates).

Usage:
    # Ingest all 5 knowledge sources
    python -m scripts.ingest_knowledge

    # Ingest a specific source only
    python -m scripts.ingest_knowledge --source renewal_policies
    python -m scripts.ingest_knowledge --source tenant_faq
    python -m scripts.ingest_knowledge --source lease_policies
    python -m scripts.ingest_knowledge --source move_in_guidelines
    python -m scripts.ingest_knowledge --source move_out_guidelines

    # Preview chunks without embedding (dry run)
    python -m scripts.ingest_knowledge --dry-run

    # Check collection stats
    python -m scripts.ingest_knowledge --stats
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.rag.documents import (
    ALL_DOCUMENTS,
    LEASE_POLICIES,
    TENANT_FAQ,
    MOVE_IN_GUIDELINES,
    MOVE_OUT_GUIDELINES,
    RENEWAL_POLICIES,
    SOURCE_LABELS,
)
from app.rag.pipeline import IngestionPipeline, TextChunker
from app.vector.qdrant_client import QdrantService


SOURCE_MAP = {
    "lease_policies": LEASE_POLICIES,
    "tenant_faq": TENANT_FAQ,
    "move_in_guidelines": MOVE_IN_GUIDELINES,
    "move_out_guidelines": MOVE_OUT_GUIDELINES,
    "renewal_policies": RENEWAL_POLICIES,
}


# ── Dry run: preview chunks without embedding ─────────────────────────────────

def dry_run(documents: list[dict], chunk_size: int = 800, overlap: int = 120) -> None:
    chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
    total_chunks = 0
    for doc in documents:
        chunks = chunker.chunk(doc["text"], title=doc.get("title", ""))
        source = SOURCE_LABELS.get(doc["source"], doc["source"])
        print(f"\n{'─' * 60}")
        print(f"  Source : {source}")
        print(f"  Title  : {doc.get('title', '(no title)')}")
        print(f"  Chunks : {len(chunks)}")
        for i, chunk in enumerate(chunks):
            print(f"\n  [{i + 1}] ({len(chunk)} chars)")
            # Show first 200 chars of each chunk as preview
            preview = chunk[:200].replace("\n", " ")
            print(f"      {preview}{'...' if len(chunk) > 200 else ''}")
        total_chunks += len(chunks)

    print(f"\n{'═' * 60}")
    print(f"  Total documents : {len(documents)}")
    print(f"  Total chunks    : {total_chunks}")
    print(f"  Avg chunk size  : {sum(len(c) for d in documents for c in chunker.chunk(d['text'], title=d.get('title', ''))) // max(total_chunks, 1)} chars")
    print(f"  (Dry run — nothing was embedded or uploaded)")


# ── Collection stats ──────────────────────────────────────────────────────────

async def show_stats() -> None:
    from qdrant_client import AsyncQdrantClient
    from app.config import settings

    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    try:
        info = await client.get_collection(settings.QDRANT_COLLECTION)
        print(f"\nQdrant Collection: {settings.QDRANT_COLLECTION}")
        print(f"  Vectors count  : {info.vectors_count}")
        print(f"  Points count   : {info.points_count}")
        print(f"  Status         : {info.status}")

        # Count by source using scroll
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        for source_key, label in SOURCE_LABELS.items():
            result, _ = await client.scroll(
                collection_name=settings.QDRANT_COLLECTION,
                scroll_filter=Filter(
                    must=[FieldCondition(key="source", match=MatchValue(value=source_key))]
                ),
                limit=1,
                with_payload=False,
                with_vectors=False,
            )
            # scroll returns (points, next_page_offset)
            # Use count instead for accuracy
            count_result = await client.count(
                collection_name=settings.QDRANT_COLLECTION,
                count_filter=Filter(
                    must=[FieldCondition(key="source", match=MatchValue(value=source_key))]
                ),
            )
            print(f"  {label:<28}: {count_result.count} chunks")
    finally:
        await client.close()


# ── Main ingestion run ────────────────────────────────────────────────────────

async def run_ingestion(documents: list[dict]) -> None:
    pipeline = IngestionPipeline()
    try:
        # Ensure collection exists before ingesting
        qdrant = QdrantService()
        await qdrant.ensure_collection()
        await qdrant.close()

        stats = await pipeline.ingest(documents)
        print(f"\n{'═' * 60}")
        print(f"  Ingestion complete")
        print(f"  Documents : {stats['documents']}")
        print(f"  Chunks    : {stats['chunks']}")
        print(f"  Upserted  : {stats['upserted']}")
        print(f"\n  Run with --stats to verify the collection.")
    finally:
        await pipeline.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest knowledge documents into the Qdrant RAG store."
    )
    parser.add_argument(
        "--source",
        choices=list(SOURCE_MAP.keys()),
        default=None,
        help="Ingest a specific source only. Defaults to all sources.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview chunks without embedding or uploading.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show Qdrant collection statistics and exit.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Maximum characters per chunk (default 800).",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=120,
        help="Overlap characters between chunks (default 120).",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    if args.stats:
        await show_stats()
        return

    documents = SOURCE_MAP[args.source] if args.source else ALL_DOCUMENTS

    source_label = SOURCE_LABELS.get(args.source, "all sources") if args.source else "all sources"
    print(f"\nLease Manager Agent — RAG Ingestion")
    print(f"  Source     : {source_label}")
    print(f"  Documents  : {len(documents)}")
    print(f"  Chunk size : {args.chunk_size} chars")
    print(f"  Overlap    : {args.overlap} chars")

    if args.dry_run:
        print(f"\n  [DRY RUN — no API calls will be made]\n")
        dry_run(documents, chunk_size=args.chunk_size, overlap=args.overlap)
    else:
        print()
        await run_ingestion(documents)


if __name__ == "__main__":
    asyncio.run(main())
