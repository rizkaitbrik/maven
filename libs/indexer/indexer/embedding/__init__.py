# Base class
from langchain_core.embeddings import Embeddings

# Direct imports (will fail if package not installed)
try:
    from langchain_openai import OpenAIEmbeddings
except ImportError:
    OpenAIEmbeddings = None

try:
    from langchain_ollama import OllamaEmbeddings
except ImportError:
    OllamaEmbeddings = None

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    HuggingFaceEmbeddings = None


def create_embeddings(
        provider: str = "openai",
        **kwargs,
) -> Embeddings:
    """Factory function to create embeddings.

    Args:
        provider: "openai", "ollama", or "huggingface"
        **kwargs: Provider-specific arguments

    Returns:
        Embeddings instance

    Example:
        embeddings = create_embeddings("openai", model="text-embedding-3-small")
        embeddings = create_embeddings("ollama", model="nomic-embed-text")
    """
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(**kwargs)
    elif provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(**kwargs)
    elif provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings
        model = kwargs.pop("model", kwargs.pop("model_name", "sentence-transformers/all-MiniLM-L6-v2"))
        return HuggingFaceEmbeddings(model_name=model, **kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}")


__all__ = [
    "Embeddings",
    "OpenAIEmbeddings",
    "OllamaEmbeddings",
    "HuggingFaceEmbeddings",
    "create_embeddings",
]