from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State for the ReAct agent graph.
    
    Uses LangGraph's message annotation for automatic message handling.
    """
    messages: Annotated[list[BaseMessage], add_messages]


class PlanningState(AgentState):
    """Extended state for plan-and-execute agents (future use)."""
    plan: list[str]
    current_step: int
    step_results: list[str]
