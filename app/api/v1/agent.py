"""
app/api/v1/agent.py
--------------------
Conversational agent endpoints.

POST /api/v1/agent/chat       — single-turn, returns full response
GET  /api/v1/agent/stream     — streaming SSE for progressive output
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage

from app.agent.graph import build_graph
from app.dependencies import DBSession, QdrantDep
from app.schemas.agent import AgentRequest, AgentResponse

router = APIRouter(prefix="/agent", tags=["Agent"])

# In-process checkpointer (dev). Swap for AsyncPostgresSaver in production.
_checkpointer = MemorySaver()


@router.post("/chat", response_model=AgentResponse)
async def chat(request: AgentRequest, db: DBSession, qdrant: QdrantDep):
    """
    Single-turn agent invocation. The thread_id maintains conversation history
    across multiple calls via the checkpointer.
    """
    graph = build_graph(session=db, qdrant=qdrant, checkpointer=_checkpointer)
    config = {"configurable": {"thread_id": request.thread_id}}

    state_update: dict = {
        "messages": [HumanMessage(content=request.message)],
        "step_count": 0,
    }
    if request.tenant_id:
        state_update["current_tenant_id"] = request.tenant_id
    if request.lease_id:
        state_update["current_lease_id"] = request.lease_id
    if request.unit_id:
        state_update["current_unit_id"] = request.unit_id

    result = await graph.ainvoke(state_update, config=config)

    from langchain_core.messages import AIMessage
    last = result["messages"][-1]
    response_text = last.content if isinstance(last, AIMessage) else str(last)

    return AgentResponse(response=response_text, thread_id=request.thread_id)


@router.get("/stream")
async def stream_chat(message: str, thread_id: str, db: DBSession, qdrant: QdrantDep):
    """
    Server-Sent Events stream. Each event contains a text chunk.
    Connect via EventSource or fetch with ReadableStream.
    """
    graph = build_graph(session=db, qdrant=qdrant, checkpointer=_checkpointer)
    config = {"configurable": {"thread_id": thread_id}}
    state_update = {
        "messages": [HumanMessage(content=message)],
        "step_count": 0,
    }

    async def event_generator():
        from langchain_core.messages import AIMessage
        async for snapshot in graph.astream(
            state_update, config=config, stream_mode="values"
        ):
            last = snapshot["messages"][-1]
            if isinstance(last, AIMessage) and last.content and not last.tool_calls:
                yield f"data: {last.content}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
