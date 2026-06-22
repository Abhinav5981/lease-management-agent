"""
app/api/v1/agent.py
--------------------
Conversational Lease Manager Agent endpoints.

POST /api/v1/agent/chat    — single-turn, returns full text response.
POST /api/v1/agent/stream  — Server-Sent Events, streams text chunks as they arrive.

Conversation memory
────────────────────
Both endpoints accept a `thread_id` that keys the conversation in the
MemorySaver checkpointer. Sending the same thread_id across calls continues
the same conversation — the agent has full history of prior turns.

The `step_count` field is reset to 0 on every new user message so the
MAX_STEPS guard restarts cleanly for each turn.
"""

import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import build_graph
from app.dependencies import DBSession, QdrantDep
from app.schemas.agent import AgentRequest, AgentResponse

router = APIRouter(prefix="/agent", tags=["Agent"])

# Shared in-process checkpointer.
# In production, replace with:
#   from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
#   checkpointer = await AsyncPostgresSaver.from_conn_string(DATABASE_URL)
_checkpointer = MemorySaver()


def _thread_config(thread_id: str) -> dict:
    """Build the LangGraph config dict for a given thread."""
    return {"configurable": {"thread_id": thread_id}}


def _initial_state(request: AgentRequest) -> dict:
    """
    Build the state update for a new user turn.
    step_count always resets to 0 so MAX_STEPS is per-turn, not cumulative.
    Entity context fields are set only when the caller passes them explicitly
    (e.g. a frontend pre-seeding context from a URL parameter).
    """
    state: dict = {
        "messages": [HumanMessage(content=request.message)],
        "step_count": 0,
    }
    if request.tenant_id:
        state["current_tenant_id"] = request.tenant_id
    if request.lease_id:
        state["current_lease_id"] = request.lease_id
    if request.unit_id:
        state["current_unit_id"] = request.unit_id
    return state


def _last_ai_text(result: dict) -> str:
    """Extract the final AIMessage text from an ainvoke result."""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return "I was unable to generate a response. Please try again."


# ── POST /api/v1/agent/chat ───────────────────────────────────────────────────

@router.post("/chat", response_model=AgentResponse)
async def chat(request: AgentRequest, db: DBSession, qdrant: QdrantDep):
    """
    Single-turn agent call. Blocks until the full response is ready.

    The thread_id ties this turn to prior conversation history.
    Use a stable per-user/session identifier (e.g. a UUID generated on the
    frontend when the chat window opens).

    Example queries the agent handles:
    - "Show leases expiring next month"
    - "Which units are available in Dubai Marina?"
    - "Create a lease for Ahmed Al-Rashid in unit X starting 2026-07-01"
    - "Raise a maintenance request for AC issue in unit 101"
    """
    try:
        graph = build_graph(session=db, qdrant=qdrant, checkpointer=_checkpointer)
        result = await graph.ainvoke(
            _initial_state(request),
            config=_thread_config(request.thread_id),
        )
        return AgentResponse(
            response=_last_ai_text(result),
            thread_id=request.thread_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {exc}",
        )


# ── POST /api/v1/agent/stream ─────────────────────────────────────────────────

@router.post("/stream")
async def stream_chat(request: AgentRequest, db: DBSession, qdrant: QdrantDep):
    """
    Streaming Server-Sent Events endpoint.

    Each event is a JSON object:
      {"type": "chunk",  "data": "<text fragment>"}   — partial AI output
      {"type": "done",   "thread_id": "<id>"}          — stream complete
      {"type": "error",  "detail": "<message>"}        — fatal error

    Connect via the browser's EventSource API or fetch + ReadableStream.
    The POST body is the same AgentRequest schema as /chat.
    """
    async def event_generator():
        try:
            graph = build_graph(session=db, qdrant=qdrant, checkpointer=_checkpointer)
            async for event in graph.astream_events(
                _initial_state(request),
                config=_thread_config(request.thread_id),
                version="v2",
            ):
                kind = event.get("event")

                # Stream individual text chunks from the LLM as they arrive
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        payload = json.dumps({"type": "chunk", "data": chunk.content})
                        yield f"data: {payload}\n\n"

            # Signal completion
            yield f"data: {json.dumps({'type': 'done', 'thread_id': request.thread_id})}\n\n"

        except Exception as exc:
            error_payload = json.dumps({"type": "error", "detail": str(exc)})
            yield f"data: {error_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
        },
    )
