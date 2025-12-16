from typing import AsyncIterator

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from tools.registry import ToolRegistry
from agents.models.config import AgentConfig
from agents.models.agents import AgentResponse
from agents.llm import create_llm
from agents.graphs import create_react_graph
from agents.checkpoints import create_checkpointer


class Agent:
    """Maven agent - facade over LangGraph.

    Provides a simple interface while allowing full LangGraph control underneath.

    Example:
        # Simple usage (context manager recommended for persistent checkpointers)
        with Agent(registry=registry) as agent:
            response = agent.run("Find Python files")

        # Or without context manager (works fine for memory backend)
        agent = Agent(registry=registry)
        response = agent.run("Find Python files")

        # With conversation memory
        response = agent.run("What files did you find?", thread_id="abc123")

        # Access underlying graph for advanced usage
        graph = agent.graph
    """

    def __init__(
            self,
            config: AgentConfig | None = None,
            registry: ToolRegistry | None = None,
            tools: list[BaseTool] | None = None,
    ):
        """Initialize the agent.

        Args:
            config: Agent configuration
            registry: Tool registry to load tools from
            tools: Direct list of tools (alternative to registry)
        """
        self.config = config or AgentConfig()

        # Create LLM
        self.llm = create_llm(self.config.llm)

        # Get tools
        self.tools: list[BaseTool] = tools or []
        if registry:
            self.tools.extend(registry.list_all())

        # Create checkpointer for memory
        # We manage the context manager lifecycle manually to keep it alive
        self._checkpointer_cm = create_checkpointer(self.config.memory)
        self.checkpointer = self._checkpointer_cm.__enter__()

        # Build the graph
        self.graph: CompiledStateGraph = create_react_graph(
            llm=self.llm,
            tools=self.tools,
            system_prompt=self.config.system_prompt,
            checkpointer=self.checkpointer,
            interrupt_before=self.config.interrupt_before,
            interrupt_after=self.config.interrupt_after,
        )

    def run(
            self,
            prompt: str,
            thread_id: str | None = None,
    ) -> AgentResponse:
        """Run the agent synchronously.

        Args:
            prompt: User prompt
            thread_id: Optional thread ID for conversation memory

        Returns:
            AgentResponse with the result
        """
        config = {}
        if thread_id and self.checkpointer:
            config["configurable"] = {"thread_id": thread_id}

        result = self.graph.invoke(
            {"messages": [HumanMessage(content=prompt)]},
            config=config,
        )

        return self._process_result(result)

    async def arun(
            self,
            prompt: str,
            thread_id: str | None = None,
    ) -> AgentResponse:
        """Run the agent asynchronously.

        Args:
            prompt: User prompt
            thread_id: Optional thread ID for conversation memory

        Returns:
            AgentResponse with the result
        """
        config = {}
        if thread_id and self.checkpointer:
            config["configurable"] = {"thread_id": thread_id}

        result = await self.graph.ainvoke(
            {"messages": [HumanMessage(content=prompt)]},
            config=config,
        )

        return self._process_result(result)

    async def astream(
            self,
            prompt: str,
            thread_id: str | None = None,
    ) -> AsyncIterator[dict]:
        """Stream agent execution events.

        Yields events as they happen, useful for real-time UI updates.

        Args:
            prompt: User prompt
            thread_id: Optional thread ID for conversation memory

        Yields:
            Event dictionaries with type and data
        """
        config = {}
        if thread_id and self.checkpointer:
            config["configurable"] = {"thread_id": thread_id}

        async for event in self.graph.astream_events(
                {"messages": [HumanMessage(content=prompt)]},
                config=config,
                version="v2",
        ):
            yield event

    def _process_result(self, result: dict) -> AgentResponse:
        """Process the graph result into AgentResponse."""
        messages = result.get("messages", [])

        # Find the final AI response
        content = ""
        tool_calls = []

        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                content = msg.content or ""
                if msg.tool_calls:
                    tool_calls = [tc for tc in msg.tool_calls]
                break

        # Count iterations (tool call rounds)
        iterations = sum(1 for m in messages if isinstance(m, AIMessage) and m.tool_calls)

        return AgentResponse(
            content=content,
            messages=messages,
            tool_calls=tool_calls,
            iterations=iterations,
        )

    def get_history(self, thread_id: str) -> list[BaseMessage]:
        """Get conversation history for a thread.

        Args:
            thread_id: Thread ID

        Returns:
            List of messages in the conversation
        """
        if not self.checkpointer:
            return []

        state = self.graph.get_state({"configurable": {"thread_id": thread_id}})
        return state.values.get("messages", [])

    def clear_history(self, thread_id: str) -> None:
        """Clear conversation history for a thread.

        Args:
            thread_id: Thread ID
        """
        # Implementation depends on checkpointer type
        # For now, this is a placeholder
        pass

    def close(self) -> None:
        """Clean up resources (close checkpointer connections)."""
        if hasattr(self, '_checkpointer_cm') and self._checkpointer_cm is not None:
            self._checkpointer_cm.__exit__(None, None, None)

    def __enter__(self) -> "Agent":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - clean up resources."""
        self.close()