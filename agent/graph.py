"""
agent/graph.py
--------------
LangGraph StateGraph — Lease Management Agent.

Architecture
────────────

    START
      │
      ▼
  ┌─────────┐   has tool_calls?   ┌───────────┐
  │  agent  │ ──────YES──────────► │   tools   │
  │  (LLM)  │ ◄────────────────── │ (ToolNode)│
  └─────────┘   always loop back  └───────────┘
      │
      │  no tool_calls  OR  step_count >= MAX_STEPS
      ▼
     END

Nodes
──────
• agent  — Invokes the LLM (GPT-4o) with the full message history and system
           prompt. Increments step_count. Clears the error field.
• tools  — LangGraph's built-in ToolNode. Executes all tool_calls emitted by
           the LLM in the previous agent turn, in parallel if multiple.
           On tool execution failure, ToolNode inserts a ToolMessage with the
           exception text so the LLM can reason about it.

Router  (should_continue)
──────────────────────────
• "tools"  — last AIMessage contains tool_calls and step_count < MAX_STEPS.
• "end"    — no tool_calls (final answer ready) OR step_count >= MAX_STEPS
             (runaway loop guard).

Memory
───────
• Short-term  — messages list in LeaseAgentState; persisted across ainvoke()
                calls via the checkpointer (keyed by thread_id).
• Long-term   — PostgreSQL checkpointer in production (AsyncPostgresSaver);
                MemorySaver for local dev.
• Entity ctx  — current_tenant_id / current_lease_id / current_unit_id survive
                the session so re-lookup round trips are avoided.

Checkpointer swap
──────────────────
Dev:        build_graph(checkpointer=MemorySaver())
Production: build_graph(checkpointer=await AsyncPostgresSaver.from_conn_string(dsn))
"""

import os
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import ToolNode

from .prompts import get_system_prompt
from .state import MAX_STEPS, LeaseAgentState
from .tools import ALL_TOOLS


# ── LLM factory ────────────────────────────────────────────────────────────

def _build_llm() -> AzureChatOpenAI:
    """
    Build the Azure OpenAI chat model.
    temperature=0  — deterministic tool selection; no creative drift.
    max_retries=2  — handles transient 429 / 503 from the API.
    """
    return AzureChatOpenAI(
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        api_version=os.environ.get("OPENAI_API_VERSION", "2024-05-01-preview"),
        temperature=0,
        max_tokens=2048,
        timeout=60,
        max_retries=2,
    )


# ══════════════════════════════════════════════════════════════════════════
# NODE: agent
# ══════════════════════════════════════════════════════════════════════════

def _build_agent_node(llm_with_tools):
    """
    Closure that captures the bound LLM and returns the agent node function.

    The system prompt is prepended on every invocation so that today's date
    is always current. The rest of the messages come from the state (full
    conversation history loaded from the checkpointer).
    """

    def agent_node(state: LeaseAgentState) -> dict:
        messages = [SystemMessage(content=get_system_prompt())] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {
            "messages": [response],
            # Increment step counter — checked in the router
            "step_count": state.get("step_count", 0) + 1,
            # Clear any previous error on a new LLM turn
            "error": None,
        }

    return agent_node


# ══════════════════════════════════════════════════════════════════════════
# ROUTER: should_continue
# ══════════════════════════════════════════════════════════════════════════

def should_continue(state: LeaseAgentState) -> Literal["tools", "end"]:
    """
    Decide whether to route to the tools node or end the ReAct loop.

    Routing logic:
    1. MAX_STEPS exceeded  → end  (prevents infinite loops on bad LLM output)
    2. LLM emitted tool_calls → tools
    3. No tool_calls          → end  (final answer is ready)
    """
    if state.get("step_count", 0) >= MAX_STEPS:
        return "end"

    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"


# ══════════════════════════════════════════════════════════════════════════
# GRAPH FACTORY
# ══════════════════════════════════════════════════════════════════════════

def build_graph(checkpointer=None) -> CompiledGraph:
    """
    Build and compile the LangGraph Lease Management Agent.

    Args:
        checkpointer: Conversation persistence backend.
                      • MemorySaver()                         — dev / testing
                      • AsyncPostgresSaver.from_conn_string() — production

    Returns:
        A compiled LangGraph graph ready for ainvoke() / astream().

    Example (dev):
        from langgraph.checkpoint.memory import MemorySaver
        graph = build_graph(checkpointer=MemorySaver())

    Example (production):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        async with AsyncPostgresSaver.from_conn_string(dsn) as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
    """
    llm = _build_llm()
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    agent_node = _build_agent_node(llm_with_tools)

    # ToolNode handles parallel tool execution and wraps errors into
    # ToolMessages so the LLM can reason about failures gracefully.
    tool_node = ToolNode(ALL_TOOLS)

    graph = StateGraph(LeaseAgentState)

    # ── Register nodes ────────────────────────────────────────────────────
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    # ── Edges ─────────────────────────────────────────────────────────────
    graph.add_edge(START, "agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )

    # After tools execute, always return to the agent for the next reasoning step
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer)
