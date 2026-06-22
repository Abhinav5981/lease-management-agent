"""
agent/state.py
--------------
LangGraph state schema for the Lease Management Agent.

Design decisions
────────────────
• messages       — full conversation history; merged by add_messages reducer so
                   each ainvoke() call appends rather than replaces.
• current_*      — entity context resolved during a session. Once the agent
                   identifies a tenant/lease/unit, it is stored here so
                   subsequent tool calls skip the re-lookup round trip.
• step_count     — reset to 0 on every ainvoke() call; guards against runaway
                   ReAct loops (ceiling: MAX_STEPS).
• error          — cleared at the start of each agent node turn; set by the
                   graph when MAX_STEPS is exceeded.
"""

from typing import Annotated, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

# Hard ceiling on ReAct loop iterations per user turn.
# Prevents infinite tool-call chains on malformed LLM responses.
MAX_STEPS: int = 10


class LeaseAgentState(TypedDict):
    # ── Conversation ──────────────────────────────────────────────────────
    # add_messages is a reducer: new messages are appended to the list,
    # not replaced. The full history survives across ainvoke() calls when
    # a checkpointer is attached.
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Session-scoped entity context ─────────────────────────────────────
    # Set when the agent resolves an entity; reused within the same thread
    # to avoid redundant tool calls.
    current_tenant_id: Optional[str]
    current_lease_id: Optional[str]
    current_unit_id: Optional[str]

    # ── Loop guard ────────────────────────────────────────────────────────
    step_count: int

    # ── Error state ───────────────────────────────────────────────────────
    error: Optional[str]
