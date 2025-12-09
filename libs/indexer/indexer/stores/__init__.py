# Base class
from langchain_core.vectorstores import VectorStore

# Chroma implementation
try:
    from langchain_chroma import Chroma
except ImportError:
    Chroma = None

# Document class (useful for working with stores)
from langchain_core.documents import Document


def create_chroma_store(
        collection_name: str = "maven",
        embedding_function = None,
        persist_directory: str | None = None,
) -> Chroma:
    """Factory function to create a Chroma store.

    Args:
        collection_name: Name of the collection
        embedding_function: LangChain Embeddings instance
        persist_directory: Directory to persist data (None for in-memory)

    Returns:
        Chroma vector store instance

    Example:
        from langchain_openai import OpenAIEmbeddings

        store = create_chroma_store(
            collection_name="maven",
            embedding_function=OpenAIEmbeddings(),
            persist_directory="~/.maven/chroma",
        )
    """
    from langchain_chroma import Chroma

    return Chroma(
        collection_name=collection_name,
        embedding_function=embedding_function,
        persist_directory=persist_directory,
    )


__all__ = [
    "VectorStore",
    "Chroma",
    "Document",
    "create_chroma_store",
]