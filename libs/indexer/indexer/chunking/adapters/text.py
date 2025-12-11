"""Text chunker using LangChain's text splitters."""

from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from indexer.models.chunking import Chunk, ChunkingConfig


class TextChunker:
    """Chunks text using recursive character splitting.

    Uses LangChain's RecursiveCharacterTextSplitter which tries to
    split on natural boundaries (paragraphs, sentences, words).

    Usage:
        chunker = TextChunker(chunk_size=1000, chunk_overlap=200)
        chunks = chunker.chunk(text, doc_id="doc123")
    """

    def __init__(
            self,
            chunk_size: int = 1000,
            chunk_overlap: int = 200,
            separators: list[str] | None = None,
    ):
        """Initialize the text chunker.

        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks
            separators: Custom separators (default: paragraphs, lines, sentences, words)
        """
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._separators = separators or ["\n\n", "\n", ". ", ", ", " "]

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self._separators,
            length_function=len,
        )

    @property
    def name(self) -> str:
        return "TextChunker"

    def chunk(
            self,
            text: str,
            doc_id: str,
            metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Split text into chunks.

        Args:
            text: Text content to chunk
            doc_id: Parent document ID
            metadata: Metadata to attach to each chunk

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        base_metadata = metadata or {}

        # Split text
        texts = self._splitter.split_text(text)

        chunks = []
        for i, content in enumerate(texts):
            chunk_id = Chunk.generate_id(doc_id, i)

            chunk_metadata = {
                **base_metadata,
                "chunker": self.name,
                "chunk_index": i,
                "total_chunks": len(texts),
            }

            chunks.append(Chunk(
                id=chunk_id,
                content=content,
                doc_id=doc_id,
                index=i,
                metadata=chunk_metadata,
            ))

        return chunks

    @classmethod
    def from_config(cls, config: ChunkingConfig) -> "TextChunker":
        """Create chunker from config."""
        return cls(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=config.separators,
        )