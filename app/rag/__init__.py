"""
app/rag/
--------
RAG (Retrieval-Augmented Generation) subsystem for the Lease Manager Agent.

Layers
──────
  documents.py  — Knowledge base content (5 sources: lease policies, tenant FAQ,
                  move-in/move-out guidelines, renewal policies).
  pipeline.py   — Ingestion pipeline: text chunking → batch embedding → Qdrant upsert.
  retriever.py  — Retrieval pipeline: query embedding → Qdrant search → context formatting.

Entry points
────────────
  Ingestion:  python -m scripts.ingest_knowledge
  Retrieval:  from app.rag.retriever import RAGRetriever
"""
