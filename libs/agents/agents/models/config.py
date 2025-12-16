from dataclasses import dataclass, field
from typing import Literal


@dataclass
class LLMConfig:
    """Configuration for Language Model (LLM) settings.
    
    Example:
        # OpenAI (default)
        config = LLMConfig()
        
        # Anthropic Claude
        config = LLMConfig(provider="anthropic", model_name="claude-3-5-sonnet-20241022")
        
        # Local Ollama
        config = LLMConfig(provider="ollama", model_name="llama3.2")
        
        # OpenAI-compatible API (e.g., Together, vLLM)
        config = LLMConfig(
            provider="openai",
            model_name="meta-llama/Llama-3.1-70B-Instruct",
            base_url="https://api.together.xyz/v1",
            api_key="your-api-key",
        )
    """
    provider: Literal["openai", "ollama", "anthropic"] = "openai"
    model_name: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4096
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    api_key: str | None = None  # None = use environment variable
    base_url: str | None = None  # None = use default provider URL

@dataclass
class MemoryConfig:
    enabled: bool = True
    backend: Literal["memory", "redis", "sqlite"] = "memory"
    db_path: str = "~/.maven/checkpoints.db"
    redis_host: str | None = None
    redis_port: int | None = None
    redis_db: int | None = None

@dataclass
class AgentConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    max_iterations: int = 10
    system_prompt: str | None = None
    recursion_limit: int = 50
    interrupt_before: list[str] = field(default_factory=list)
    interrupt_after: list[str] = field(default_factory=list)