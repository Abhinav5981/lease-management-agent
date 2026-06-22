"""
app/rag/retriever.py
---------------------
Retrieval pipeline for the Lease Manager Agent RAG system.

RAGRetriever wraps QdrantService and adds:
  1. Source-aware filtering — restrict search to a specific knowledge source
     (e.g. only renewal_policies when answering renewal questions).
  2. Context formatting — converts raw Qdrant hits into a numbered, source-
     attributed context block that the LLM can directly incorporate into its answer.
  3. Graceful empty handling — returns a clear "no results" message so the LLM
     knows to fall back to its own knowledge rather than hallucinating citations.

Integration
────────────
  The knowledge_search tool in app/agent/tools.py calls RAGRetriever.retrieve()
  and returns the formatted context string as a tool result. The LLM then uses
  that context to formulate a grounded answer.
"""

from typing import Any

from app.rag.documents import SOURCE_LABELS
from app.vector.qdrant_client import QdrantService


# Map user-facing source names to internal source identifiers
# Allows the LLM to say "lease_policies" or "renewal" and still match.
_SOURCE_ALIASES: dict[str, str] = {
    # Exact keys
    "lease_policies": "lease_policies",
    "tenant_faq": "tenant_faq",
    "move_in_guidelines": "move_in_guidelines",
    "move_out_guidelines": "move_out_guidelines",
    "renewal_policies": "renewal_policies",
    # Friendly aliases the LLM might use
    "faq": "tenant_faq",
    "move_in": "move_in_guidelines",
    "move_out": "move_out_guidelines",
    "renewal": "renewal_policies",
    "lease": "lease_policies",
    "policies": "lease_policies",
}


class RAGRetriever:
    """
    Retrieval pipeline backed by Qdrant vector search.

    Args:
        qdrant: QdrantService singleton injected by the FastAPI dependency layer.
    """

    def __init__(self, qdrant: QdrantService) -> None:
        self._qdrant = qdrant

    # ── Primary interface (used by the knowledge_search tool) ─────────────────

    async def retrieve(
        self,
        query: str,
        *,
        source: str | None = None,
        doc_type: str | None = None,
        top_k: int = 4,
        score_threshold: float = 0.45,
    ) -> dict[str, Any]:
        """
        Retrieve relevant knowledge chunks and return a formatted context block.

        Args:
            query:           Natural-language question to search.
            source:          Optional source filter (accepts aliases like "renewal").
            doc_type:        Optional doc_type filter ("policy" | "faq" | "guideline").
            top_k:           Maximum number of chunks to return.
            score_threshold: Minimum cosine similarity (0–1). Lower = more recall.

        Returns:
            Dict with:
              "context"  : str  — formatted context ready to include in LLM prompt.
              "sources"  : list — list of source labels used (for attribution).
              "count"    : int  — number of chunks retrieved.
              "raw"      : list — raw Qdrant results (for debugging/logging).
        """
        resolved_source = _SOURCE_ALIASES.get(source or "", source)

        hits = await self._qdrant.search(
            query,
            top_k=top_k,
            source=resolved_source,
            doc_type=doc_type,
            score_threshold=score_threshold,
        )

        if not hits:
            return {
                "context": (
                    "No relevant documents were found in the knowledge base "
                    "for this query. Please answer based on general knowledge "
                    "or advise the user to contact the leasing team."
                ),
                "sources": [],
                "count": 0,
                "raw": [],
            }

        context = self._format_context(hits, query)
        source_labels = sorted({
            SOURCE_LABELS.get(h["source"], h["source"]) for h in hits
        })

        return {
            "context": context,
            "sources": source_labels,
            "count": len(hits),
            "raw": hits,
        }

    # ── Source-specific convenience methods ───────────────────────────────────

    async def retrieve_lease_policy(self, query: str, top_k: int = 3) -> dict[str, Any]:
        """Retrieve from lease policies only."""
        return await self.retrieve(query, source="lease_policies", top_k=top_k)

    async def retrieve_faq(self, query: str, top_k: int = 3) -> dict[str, Any]:
        """Retrieve from tenant FAQs only."""
        return await self.retrieve(query, source="tenant_faq", top_k=top_k)

    async def retrieve_move_in(self, query: str, top_k: int = 3) -> dict[str, Any]:
        """Retrieve from move-in guidelines only."""
        return await self.retrieve(query, source="move_in_guidelines", top_k=top_k)

    async def retrieve_move_out(self, query: str, top_k: int = 3) -> dict[str, Any]:
        """Retrieve from move-out guidelines only."""
        return await self.retrieve(query, source="move_out_guidelines", top_k=top_k)

    async def retrieve_renewal(self, query: str, top_k: int = 3) -> dict[str, Any]:
        """Retrieve from renewal policies only."""
        return await self.retrieve(query, source="renewal_policies", top_k=top_k)

    # ── Context formatter ─────────────────────────────────────────────────────

    @staticmethod
    def _format_context(hits: list[dict[str, Any]], query: str) -> str:
        """
        Format Qdrant search results into a context block for the LLM.

        Format:
          --- Knowledge Base Context ---
          Query: <query>

          [1] Source: Renewal Policies | Title: RERA 90-Day Notice Rule
          <chunk text>

          [2] Source: Lease Policies | Title: Lease Creation Requirements
          <chunk text>
          --- End of Context ---

        Numbered entries help the LLM cite sources accurately ("According to [1]...").
        """
        lines: list[str] = [
            "--- Knowledge Base Context ---",
            f"Query: {query}",
            "",
        ]

        for i, hit in enumerate(hits, 1):
            source_label = SOURCE_LABELS.get(hit["source"], hit["source"])
            title = hit.get("metadata", {}).get("title", hit["source"])
            score = hit.get("score", 0)

            lines.append(f"[{i}] Source: {source_label} | Title: {title} | Relevance: {score:.2f}")
            lines.append(hit["text"])
            lines.append("")

        lines.append("--- End of Context ---")
        return "\n".join(lines)
