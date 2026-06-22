"""
agent/__init__.py
-----------------
Public API for the Lease Management Agent.

Usage (single turn):
    from agent import run_agent
    response = await run_agent("Show me available 2BR in Dubai Marina", thread_id="user-42")

Usage (streaming):
    from agent import stream_agent
    async for token in stream_agent("Renew lease LSE-2026-000001", thread_id="user-42"):
        print(token, end="", flush=True)
"""

from typing import AsyncIterator, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from .db import close_pool, get_pool
from .graph import build_graph
from .state import LeaseAgentState

__all__ = [
    "build_graph",
    "get_pool",
    "close_pool",
    "run_agent",
    "stream_agent",
]

# ── Default graph (dev — MemorySaver checkpointer) ─────────────────────────
# For production, build the graph explicitly with AsyncPostgresSaver:
#
#   from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
#   async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as cp:
#       graph = build_graph(checkpointer=cp)
#
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph(checkpointer=MemorySaver())
    return _graph


# ── run_agent ──────────────────────────────────────────────────────────────

async def run_agent(
    message: str,
    thread_id: str,
    *,
    tenant_id: Optional[str] = None,
    lease_id: Optional[str] = None,
    unit_id: Optional[str] = None,
) -> str:
    """
    Run one conversational turn and return the agent's final text response.

    The checkpointer (keyed by thread_id) automatically restores the full
    conversation history so multi-turn context is preserved across calls.

    Args:
        message:   The user's message.
        thread_id: Unique identifier for the conversation thread (e.g. user ID,
                   session ID, or ticket number). Determines which checkpoint
                   is loaded/saved.
        tenant_id: Optional — pre-seed the entity context when the caller
                   already knows which tenant is involved.
        lease_id:  Optional — pre-seed the lease context.
        unit_id:   Optional — pre-seed the unit context.

    Returns:
        The agent's final plain-text response for this turn.
    """
    graph = _get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    # step_count is reset to 0 on every turn (the MAX_STEPS guard is per-turn,
    # not per-session). Optional entity context is passed only when provided by
    # the caller; the checkpointer preserves values from previous turns otherwise.
    state_update: dict = {
        "messages": [HumanMessage(content=message)],
        "step_count": 0,
    }
    if tenant_id is not None:
        state_update["current_tenant_id"] = tenant_id
    if lease_id is not None:
        state_update["current_lease_id"] = lease_id
    if unit_id is not None:
        state_update["current_unit_id"] = unit_id

    result = await graph.ainvoke(state_update, config=config)

    last = result["messages"][-1]
    return last.content if isinstance(last, AIMessage) else str(last)


# ── stream_agent ───────────────────────────────────────────────────────────

async def stream_agent(
    message: str,
    thread_id: str,
) -> AsyncIterator[str]:
    """
    Stream agent state snapshots, yielding the content of each new AI message.

    Useful for SSE / WebSocket endpoints where progressive output improves UX.
    Intermediate tool-call messages are filtered out; only final AI text is yielded.
    """
    graph = _get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    state_update = {
        "messages": [HumanMessage(content=message)],
        "step_count": 0,
    }

    async for snapshot in graph.astream(
        state_update, config=config, stream_mode="values"
    ):
        last = snapshot["messages"][-1]
        # Only surface final AI responses (not mid-loop tool call messages)
        if isinstance(last, AIMessage) and last.content and not last.tool_calls:
            yield last.content
