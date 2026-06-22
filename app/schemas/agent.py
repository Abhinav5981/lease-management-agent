"""
app/schemas/agent.py
---------------------
Request/response schemas for the conversational agent endpoint.
"""

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str = Field(
        description="Unique conversation thread ID. Use a stable identifier per user/session."
    )
    # Optional entity context — pre-seeds agent state when the caller
    # already knows which entity is in focus.
    tenant_id: str | None = None
    lease_id: str | None = None
    unit_id: str | None = None


class AgentResponse(BaseModel):
    response: str
    thread_id: str


class AgentStreamChunk(BaseModel):
    chunk: str
    thread_id: str
    done: bool = False
