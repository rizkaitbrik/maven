"""Code chunker using AST segments or language-aware splitting."""

from typing import Any

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from libs.indexer.indexer.models.chunking import Chunk, ChunkingConfig

# Map language names to LangChain Language enum
LANGUAGE_MAP = {
    "python": Language.PYTHON,
    "javascript": Language.JS,
    "typescript": Language.TS,
    "java": Language.JAVA,
    "kotlin": Language.KOTLIN,
    "go": Language.GO,
    "rust": Language.RUST,
    "ruby": Language.RUBY,
    "php": Language.PHP,
    "cpp": Language.CPP,
    "c": Language.C,
    "csharp": Language.CSHARP,
    "scala": Language.SCALA,
    "swift": Language.SWIFT,
    "lua": Language.LUA,
    "perl": Language.PERL,
    "haskell": Language.HASKELL,
    "markdown": Language.MARKDOWN,
    "latex": Language.LATEX,
    "html": Language.HTML,
    "sol": Language.SOL,
}


class CodeChunker:
    """Chunks code using AST segments or language-aware splitting.

    Two modes:
    1. AST mode: Uses pre-parsed AST segments (functions, classes)
    2. Fallback mode: Uses language-aware text splitting

    Usage:
        chunker = CodeChunker(chunk_size=1500)

        # With AST segments from CodeExtractor
        chunks = chunker.chunk_with_segments(
            text=code,
            doc_id="doc123",
            segments=extraction_result.metadata["segments"],
        )

        # Without segments (language-aware splitting)
        chunks = chunker.chunk(
            text=code,
            doc_id="doc123",
            metadata={"language": "python"},
        )
    """

    def __init__(
            self,
            chunk_size: int = 1500,
            chunk_overlap: int = 200,
            use_ast_chunks: bool = True,
    ):
        """Initialize the code chunker.

        Args:
            chunk_size: Target chunk size for large segments
            chunk_overlap: Overlap between chunks
            use_ast_chunks: Whether to use AST segments when available
        """
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._use_ast_chunks = use_ast_chunks

    @property
    def name(self) -> str:
        return "CodeChunker"

    def chunk(
            self,
            text: str,
            doc_id: str,
            metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Chunk code using language-aware splitting.

        Args:
            text: Code content
            doc_id: Parent document ID
            metadata: Must include "language" key for best results

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        base_metadata = metadata or {}
        language = base_metadata.get("language")

        # Get language-specific splitter
        splitter = self._get_splitter(language)

        # Split text
        texts = splitter.split_text(text)

        chunks = []
        for i, content in enumerate(texts):
            chunk_id = Chunk.generate_id(doc_id, i)

            chunk_metadata = {
                **base_metadata,
                "chunker": self.name,
                "chunk_index": i,
                "total_chunks": len(texts),
                "chunk_type": "code",
            }

            chunks.append(Chunk(
                id=chunk_id,
                content=content,
                doc_id=doc_id,
                index=i,
                metadata=chunk_metadata,
            ))

        return chunks

    def chunk_with_segments(
            self,
            text: str,
            doc_id: str,
            segments: list[dict[str, Any]],
            metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Chunk code using pre-parsed AST segments.

        Each segment (function, class) becomes a chunk.
        Large segments are further split.

        Args:
            text: Full code content (for fallback)
            doc_id: Parent document ID
            segments: AST segments from CodeExtractor
            metadata: Additional metadata

        Returns:
            List of Chunk objects
        """
        if not segments:
            return self.chunk(text, doc_id, metadata)

        base_metadata = metadata or {}
        chunks = []
        chunk_index = 0

        for segment in segments:
            content = segment.get("content", "")
            content_type = segment.get("content_type", "unknown")

            if not content or not content.strip():
                continue

            # If segment is too large, split it further
            if len(content) > self._chunk_size:
                sub_chunks = self._split_large_segment(
                    content=content,
                    doc_id=doc_id,
                    start_index=chunk_index,
                    base_metadata=base_metadata,
                    content_type=content_type,
                )
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)
            else:
                # Use segment as-is
                chunk_id = Chunk.generate_id(doc_id, chunk_index)

                chunk_metadata = {
                    **base_metadata,
                    "chunker": self.name,
                    "chunk_index": chunk_index,
                    "chunk_type": content_type,
                }

                chunks.append(Chunk(
                    id=chunk_id,
                    content=content,
                    doc_id=doc_id,
                    index=chunk_index,
                    metadata=chunk_metadata,
                ))
                chunk_index += 1

        # Update total_chunks in all metadata
        for chunk in chunks:
            chunk.metadata["total_chunks"] = len(chunks)

        return chunks

    def _get_splitter(self, language: str | None) -> RecursiveCharacterTextSplitter:
        """Get a language-aware splitter."""
        lc_language = LANGUAGE_MAP.get(language) if language else None

        if lc_language:
            return RecursiveCharacterTextSplitter.from_language(
                language=lc_language,
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
            )
        else:
            # Fallback to generic code splitting
            return RecursiveCharacterTextSplitter(
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
                separators=[
                    "\nclass ",
                    "\ndef ",
                    "\n\ndef ",
                    "\n\n",
                    "\n",
                    " ",
                ],
            )

    def _split_large_segment(
            self,
            content: str,
            doc_id: str,
            start_index: int,
            base_metadata: dict[str, Any],
            content_type: str,
    ) -> list[Chunk]:
        """Split a large segment into smaller chunks."""
        language = base_metadata.get("language")
        splitter = self._get_splitter(language)

        texts = splitter.split_text(content)

        chunks = []
        for i, text in enumerate(texts):
            chunk_index = start_index + i
            chunk_id = Chunk.generate_id(doc_id, chunk_index)

            chunk_metadata = {
                **base_metadata,
                "chunker": self.name,
                "chunk_index": chunk_index,
                "chunk_type": content_type,
                "is_split": True,
                "split_part": i + 1,
                "split_total": len(texts),
            }

            chunks.append(Chunk(
                id=chunk_id,
                content=text,
                doc_id=doc_id,
                index=chunk_index,
                metadata=chunk_metadata,
            ))

        return chunks

    @classmethod
    def from_config(cls, config: ChunkingConfig) -> "CodeChunker":
        """Create chunker from config."""
        return cls(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            use_ast_chunks=config.use_ast_chunks,
        )