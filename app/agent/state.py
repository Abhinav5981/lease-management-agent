"""app/agent/state.py"""
from typing import Annotated, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

MAX_STEPS: int = 10


class LeaseAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    current_tenant_id: Optional[str]
    current_lease_id: Optional[str]
    current_unit_id: Optional[str]
    step_count: int
    error: Optional[str]
