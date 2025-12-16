from dataclasses import dataclass, field
from langchain_core.messages import BaseMessage

@dataclass
class AgentResponse:
    """Response from agent execution."""
    content: str
    messages: list[BaseMessage] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    iterations: int = 0
