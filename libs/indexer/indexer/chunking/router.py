"""Chunking router - selects appropriate chunker based on content type."""

from typing import Any

from libs.indexer.indexer.chunking.adapters.code import CodeChunker
from libs.indexer.indexer.chunking.adapters.text import TextChunker
from libs.indexer.indexer.models.chunking import Chunk, ChunkingConfig


class ChunkingRouter:
    """Routes content to the appropriate chunker.

    Usage:
        router = ChunkingRouter()

        # Automatically selects chunker based on metadata
        chunks = router.chunk(
            text=content,
            doc_id="doc123",
            metadata={"language": "python", "segments": [...]}
        )
    """

    def __init__(
            self,
            config: ChunkingConfig | None = None,
    ):
        """Initialize the chunking router.

        Args:
            config: Chunking configuration
        """
        self._config = config or ChunkingConfig()
        self._text_chunker = TextChunker.from_config(self._config)
        self._code_chunker = CodeChunker.from_config(self._config)

    def chunk(
            self,
            text: str,
            doc_id: str,
            metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Chunk content using the appropriate chunker.

        Args:
            text: Content to chunk
            doc_id: Parent document ID
            metadata: Content metadata (used to select chunker)

        Returns:
            List of Chunk objects
        """
        metadata = metadata or {}

        # Determine content type
        language = metadata.get("language")
        segments = metadata.get("segments")
        extractor = metadata.get("extractor", "")

        # Code with AST segments
        if segments and self._config.use_ast_chunks:
            return self._code_chunker.chunk_with_segments(
                text=text,
                doc_id=doc_id,
                segments=segments,
                metadata=metadata,
            )

        # Code without segments
        if language or extractor == "CodeExtractor":
            return self._code_chunker.chunk(
                text=text,
                doc_id=doc_id,
                metadata=metadata,
            )

        # Default to text chunking
        return self._text_chunker.chunk(
            text=text,
            doc_id=doc_id,
            metadata=metadata,
        )

    @property
    def text_chunker(self) -> TextChunker:
        return self._text_chunker

    @property
    def code_chunker(self) -> CodeChunker:
        return self._code_chunker