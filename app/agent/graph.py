"""
app/agent/graph.py
-------------------
LangGraph graph factory for the FastAPI-integrated agent.

Key difference from the standalone graph:
• build_graph() accepts a session and qdrant service, then calls
  build_tools() to get a per-request tool list bound to that session.
  This means every HTTP request gets its own LangGraph graph instance
  with proper DB session isolation.
"""

import os
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import ToolNode
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import MAX_STEPS, LeaseAgentState
from app.agent.prompts import get_system_prompt
from app.agent.tools import build_tools
from app.vector.qdrant_client import QdrantService


def _build_llm() -> AzureChatOpenAI:
    return AzureChatOpenAI(
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        api_version=os.environ.get("OPENAI_API_VERSION", "2024-05-01-preview"),
        temperature=0,
        max_tokens=2048,
        timeout=60,
        max_retries=2,
    )


def build_graph(
    session: AsyncSession,
    qdrant: QdrantService,
    checkpointer=None,
) -> CompiledGraph:
    """
    Build a per-request compiled LangGraph graph.

    Args:
        session:      SQLAlchemy async session for this request.
        qdrant:       QdrantService singleton.
        checkpointer: Conversation memory backend (MemorySaver or AsyncPostgresSaver).
    """
    tools = build_tools(session, qdrant)
    llm = _build_llm()
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def agent_node(state: LeaseAgentState) -> dict:
        messages = [SystemMessage(content=get_system_prompt())] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {
            "messages": [response],
            "step_count": state.get("step_count", 0) + 1,
            "error": None,
        }

    def should_continue(state: LeaseAgentState) -> Literal["tools", "end"]:
        if state.get("step_count", 0) >= MAX_STEPS:
            return "end"
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "end"

    graph = StateGraph(LeaseAgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer)
