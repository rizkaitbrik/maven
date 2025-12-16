from langchain_core.language_models import BaseChatModel
from agents.models.config import LLMConfig


def create_llm(config: LLMConfig | None = None) -> BaseChatModel:
    """Factory to create a LangChain chat model.
    
    Args:
        config: LLM configuration. Defaults to OpenAI GPT-4.
        
    Returns:
        LangChain BaseChatModel instance
        
    Example:
        llm = create_llm(LLMConfig(provider="anthropic", model_name="claude-3-5-sonnet-20241022"))
        llm = create_llm(LLMConfig(provider="ollama", model_name="llama3.2"))
    """
    config = config or LLMConfig()
    provider = config.provider.lower()
    
    match provider:
        case "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=config.model_name,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                frequency_penalty=config.frequency_penalty,
                presence_penalty=config.presence_penalty,
                api_key=config.api_key or None,  # None = use env var
                base_url=config.base_url or None,
            )
        case "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=config.model_name,
                temperature=config.temperature,
                base_url=config.base_url or "http://localhost:11434",
            )
        case "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model_name=config.model_name,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                api_key=config.api_key or None,  # None = use env var
            )
        case _:
            raise ValueError(f"Unsupported LLM provider: {config.provider}")