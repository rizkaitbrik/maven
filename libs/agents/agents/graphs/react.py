from typing import Callable
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.base import BaseCheckpointSaver

from agents.models.state import AgentState
from agents.models.config import AgentConfig


DEFAULT_SYSTEM_PROMPT = """You are Maven, a helpful AI assistant for macOS.
You have access to tools to help users with file operations, search, code analysis, and more.
Be concise and accurate. Use tools when needed to accomplish tasks."""


def should_continue(state: AgentState) -> str:
    """Determine if the agent should continue or finish."""
    messages = state["messages"]
    last_message = messages[-1]

    # If the LLM makes a tool call, route to tools
    if last_message.tool_calls:
        return "tools"

    # Otherwise, finish
    return END


def create_react_graph(
        llm: BaseChatModel,
        tools: list[BaseTool],
        system_prompt: str | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        interrupt_before: list[str] | None = None,
        interrupt_after: list[str] | None = None,
):
    """Create a ReAct-style agent graph.

    This graph follows the ReAct pattern:
    1. LLM decides what to do (call tools or respond)
    2. If tools called -> execute tools -> back to LLM
    3. If no tools -> respond to user

    Args:
        llm: Chat model to use
        tools: List of tools available to the agent
        system_prompt: System prompt for the agent
        checkpointer: Optional checkpointer for memory persistence
        interrupt_before: Node names to interrupt before (human-in-the-loop)
        interrupt_after: Node names to interrupt after

    Returns:
        Compiled LangGraph
    """
    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(tools)

    # Prepare system message
    system = system_prompt or DEFAULT_SYSTEM_PROMPT

    def call_model(state: AgentState) -> dict:
        """Node that calls the LLM."""
        messages = state["messages"]

        # Prepend system message if not present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system)] + list(messages)

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # Build the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))

    # Add edges
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, ["tools", END])
    graph.add_edge("tools", "agent")

    # Compile with optional checkpointer and interrupts
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before or [],
        interrupt_after=interrupt_after or [],
    )