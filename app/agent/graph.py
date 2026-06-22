"""
app/agent/graph.py
-------------------
Lease Manager Agent — LangGraph implementation.

Architecture
────────────
                        ┌─────────────────────────────────┐
    START ──► agent ──► │  should_continue (router)        │
               ▲        │  • has tool_calls & steps < MAX? │
               │        │    → tools                       │
               │        │  • else                          │
               │        │    → END                         │
               │        └─────────────────────────────────┘
               │                  │
               │      ┌───────────▼───────────┐
               │      │       tools            │
               │      │  (ToolNode — parallel) │
               │      └───────────┬───────────┘
               │                  │
               │      ┌───────────▼───────────┐
               └──────│  extract_entity_ctx    │
                      │  (parse tool results,  │
                      │   update state IDs)    │
                      └───────────────────────┘

Nodes
──────
• agent             — Invoke GPT-4o with full conversation history + system prompt.
                      Increments step_count each turn.
• tools             — LangGraph ToolNode; executes all tool_calls in parallel.
                      Wraps execution errors into ToolMessages so the LLM can reason
                      about failures without crashing the loop.
• extract_entity_ctx — Parse the latest ToolMessages, extract tenant/lease/unit IDs,
                      and store them in state for context reuse within the session.

Memory & State
──────────────
• MemorySaver checkpointer (dev): persists full conversation in-process.
• Swap for AsyncPostgresSaver (prod) via build_graph(checkpointer=...).
• Thread ID (from AgentRequest.thread_id) keys each conversation independently.
• step_count resets to 0 on every new user turn (set in the API layer).
• current_tenant_id / current_lease_id / current_unit_id carry entity context
  across tool calls within the same session.

LLM
───
• ChatOpenAI singleton — created once at module level, reused across all requests.
  Creating a new client per request was wasteful; the OpenAI SDK client is thread/
  async-safe and stateless between calls.
• temperature=0 — deterministic tool selection; no creative drift.
• bind_tools() called per request so the bound tool schema always matches the
  tools built for that session's DB session.
"""

import json
from functools import lru_cache
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import get_system_prompt
from app.agent.state import MAX_STEPS, LeaseAgentState
from app.agent.tools import build_tools
from app.config import settings
from app.vector.qdrant_client import QdrantService


# ── LLM singleton ─────────────────────────────────────────────────────────────
# @lru_cache so _get_llm() always returns the same ChatOpenAI instance.
# ChatOpenAI is async-safe — no risk in sharing across concurrent requests.

@lru_cache(maxsize=1)
def _get_llm() -> ChatGroq:
    return ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=0,
        max_tokens=2048,
        max_retries=2,
    )


# ══════════════════════════════════════════════════════════════════════════════
# ENTITY CONTEXT EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

def _extract_entity_context(state: LeaseAgentState) -> dict:
    """
    After tools execute, scan the freshly-added ToolMessages and pull out
    entity IDs so the agent doesn't need to re-look them up mid-session.

    Rules:
    • Walk messages in reverse until we hit an AIMessage (the tool-call turn).
    • Parse each ToolMessage payload as JSON.
    • First tenant  from search_tenant / create_lease → current_tenant_id
    • Lease         from create_lease / view_lease    → current_lease_id
    • First unit    from search_properties            → current_unit_id
    """
    updates: dict = {}
    messages = state["messages"]

    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            break
        if not isinstance(msg, ToolMessage):
            continue

        try:
            data = json.loads(msg.content)
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

        # Tenant context — from search_tenant
        if "tenants" in data and isinstance(data["tenants"], list) and data["tenants"]:
            if "current_tenant_id" not in updates:
                updates["current_tenant_id"] = data["tenants"][0]["id"]

        # Lease context — from create_lease or view_lease
        lease_payload = data.get("lease") or (data.get("success") and data.get("lease"))
        if isinstance(lease_payload, dict) and "id" in lease_payload:
            if "current_lease_id" not in updates:
                updates["current_lease_id"] = lease_payload["id"]

        # create_lease also returns lease at top level when success=True
        if data.get("success") and "lease" in data and isinstance(data["lease"], dict):
            if "current_lease_id" not in updates:
                updates["current_lease_id"] = data["lease"]["id"]
            if "current_tenant_id" not in updates and "tenant_id" in data["lease"]:
                updates["current_tenant_id"] = data["lease"]["tenant_id"]

        # Unit context — from search_properties
        if "units" in data and isinstance(data["units"], list) and data["units"]:
            if "current_unit_id" not in updates:
                updates["current_unit_id"] = data["units"][0]["id"]

    return updates


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH FACTORY
# ══════════════════════════════════════════════════════════════════════════════

def build_graph(
    session: AsyncSession,
    qdrant: QdrantService,
    checkpointer=None,
):
    """
    Build a compiled LangGraph for one request lifecycle.

    A new graph is compiled per-request so each request gets its own
    SQLAlchemy session inside the tools (session isolation). The LLM
    and Qdrant client are singletons shared across requests.

    Args:
        session:      SQLAlchemy AsyncSession for this request.
        qdrant:       QdrantService singleton.
        checkpointer: Conversation memory backend.
                      Pass MemorySaver() (dev) or AsyncPostgresSaver (prod).
    """
    tools = build_tools(session, qdrant)
    llm_with_tools = _get_llm().bind_tools(tools)
    tool_node = ToolNode(tools)

    # ── Node: agent ────────────────────────────────────────────────────────

    async def agent_node(state: LeaseAgentState) -> dict:
        """
        Invoke the LLM with the full conversation history.
        The system prompt is regenerated each call so today's date is always
        current without a server restart.
        """
        messages = [SystemMessage(content=get_system_prompt())] + state["messages"]
        response = await llm_with_tools.ainvoke(messages)
        return {
            "messages": [response],
            "step_count": state.get("step_count", 0) + 1,
            "error": None,
        }

    # ── Node: extract_entity_ctx ───────────────────────────────────────────

    def entity_ctx_node(state: LeaseAgentState) -> dict:
        """
        Pure state transformation — no I/O.
        Extracts entity IDs from the latest batch of ToolMessages and
        writes them into the state for the agent's next reasoning step.
        """
        return _extract_entity_context(state)

    # ── Router ─────────────────────────────────────────────────────────────

    def should_continue(state: LeaseAgentState) -> Literal["tools", "end"]:
        """
        Route to tools if the LLM emitted tool_calls and we haven't hit MAX_STEPS.
        Route to end otherwise (final answer ready, or runaway loop guard).
        """
        if state.get("step_count", 0) >= MAX_STEPS:
            return "end"
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "end"

    # ── Graph assembly ─────────────────────────────────────────────────────

    graph = StateGraph(LeaseAgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("extract_entity_ctx", entity_ctx_node)

    graph.add_edge(START, "agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END},
    )

    # After tools execute → extract entity context → back to agent for next reasoning step
    graph.add_edge("tools", "extract_entity_ctx")
    graph.add_edge("extract_entity_ctx", "agent")

    return graph.compile(checkpointer=checkpointer)
