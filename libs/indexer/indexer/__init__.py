from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

# Chunking
from libs.indexer.indexer.models.chunking import (
    Chunk,
    ChunkingConfig,
)

from indexer.chunking.adapters.code import CodeChunker
from indexer.chunking.adapters.text import TextChunker
from indexer.chunking.interfaces.chunker import Chunker
from indexer.chunking.router import ChunkingRouter

# Embedding (re-exports)
from indexer.embedding import (
    HuggingFaceEmbeddings,
    OllamaEmbeddings,
    OpenAIEmbeddings,
    create_embeddings,
)
from indexer.extraction.adapters.code import CodeExtractor
from indexer.extraction.adapters.docx import DocxExtractor
from indexer.extraction.adapters.pdf import PDFExtractor
from indexer.extraction.adapters.text import TextExtractor
from indexer.extraction.models.extraction_result import ExtractionResult

# Extraction
from indexer.extraction.router import (
    ExtractionRouter,
    Extractor,
)
from indexer.indexer import SemanticIndexer
from indexer.models.indexing import IndexingResult

# Stores (re-exports)
from indexer.stores import Chroma, create_chroma_store

__all__ = [
    # Main
    "SemanticIndexer",
    "IndexingResult",

    # Extraction
    "ExtractionRouter",
    "ExtractionResult",
    "Extractor",
    "TextExtractor",
    "CodeExtractor",
    "PDFExtractor",
    "DocxExtractor",

    # Chunking
    "ChunkingRouter",
    "Chunk",
    "ChunkingConfig",
    "Chunker",
    "TextChunker",
    "CodeChunker",

    # LangChain base classes
    "Document",
    "VectorStore",
    "Embeddings",

    # Stores
    "Chroma",
    "create_chroma_store",

    # Embeddings
    "OpenAIEmbeddings",
    "OllamaEmbeddings",
    "HuggingFaceEmbeddings",
    "create_embeddings",
]

__version__ = "0.1.0"