"""Semantic indexer - orchestrates extraction, chunking, and storage."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from indexer.chunking.router import ChunkingRouter
from indexer.extraction.router import ExtractionRouter
from indexer.models.chunking import Chunk
from indexer.models.indexing import IndexingResult


class SemanticIndexer:
    """Orchestrates the full indexing and search pipeline.

    Uses LangChain's VectorStore which handles embeddings internally.

    Pipeline:
        File → Extractor → Chunker → VectorStore (embeds + stores)

    Usage:
        from langchain_chroma import Chroma
        from langchain_openai import OpenAIEmbeddings

        # Setup components
        extraction = ExtractionRouter()
        extraction.register(CodeExtractor(...))

        chunking = ChunkingRouter()

        # VectorStore handles embeddings internally
        store = Chroma(
            collection_name="maven",
            embedding_function=OpenAIEmbeddings(),
            persist_directory="~/.maven/chroma",
        )

        # Create indexer
        indexer = SemanticIndexer(
            extraction_router=extraction,
            chunking_router=chunking,
            store=store,
        )

        # Index files
        result = indexer.index_file("main.py")

        # Search
        results = indexer.search("authentication", k=5)
    """

    def __init__(
            self,
            extraction_router: ExtractionRouter,
            chunking_router: ChunkingRouter,
            store: VectorStore,
    ):
        """Initialize the semantic indexer.

        Args:
            extraction_router: Router for file extraction
            chunking_router: Router for content chunking
            store: LangChain VectorStore (handles embeddings internally)
        """
        self.extraction = extraction_router
        self.chunking = chunking_router
        self.store = store

    def index_file(self, path: Path | str) -> IndexingResult:
        """Index a single file.

        Args:
            path: Path to the file

        Returns:
            IndexingResult with status and metadata
        """
        path = Path(path)
        start_time = datetime.now()

        try:
            # 1. Generate document ID
            doc_id = self._generate_doc_id(path)

            # 2. Extract content
            extraction_result = self.extraction.extract(path)

            # 3. Chunk content
            chunks = self.chunking.chunk(
                text=extraction_result.text,
                doc_id=doc_id,
                metadata=extraction_result.metadata,
            )

            if not chunks:
                return IndexingResult(
                    doc_id=doc_id,
                    path=str(path),
                    chunk_count=0,
                    success=True,
                    duration_ms=self._elapsed_ms(start_time),
                )

            # 4. Prepare documents for LangChain
            documents = self._chunks_to_documents(chunks, path, doc_id)

            # 5. Add to store (embeddings computed automatically)
            ids = [chunk.id for chunk in chunks]
            self.store.add_documents(documents, ids=ids)

            return IndexingResult(
                doc_id=doc_id,
                path=str(path),
                chunk_count=len(chunks),
                success=True,
                duration_ms=self._elapsed_ms(start_time),
            )

        except Exception as e:
            return IndexingResult(
                doc_id=self._generate_doc_id(path),
                path=str(path),
                chunk_count=0,
                success=False,
                error=str(e),
                duration_ms=self._elapsed_ms(start_time),
            )

    def index_files(self, paths: list[Path | str]) -> list[IndexingResult]:
        """Index multiple files.

        Args:
            paths: List of file paths

        Returns:
            List of IndexingResult for each file
        """
        results = []
        for path in paths:
            result = self.index_file(path)
            results.append(result)
        return results

    def index_directory(
            self,
            directory: Path | str,
            recursive: bool = True,
    ) -> list[IndexingResult]:
        """Index all supported files in a directory.

        Args:
            directory: Directory path
            recursive: Whether to search recursively

        Returns:
            List of IndexingResult for each file
        """
        directory = Path(directory)

        if recursive:
            files = list(directory.rglob("*"))
        else:
            files = list(directory.glob("*"))

        # Filter to supported files only
        supported_files = [
            f for f in files
            if f.is_file() and self.extraction.supports(f)
        ]

        return self.index_files(supported_files)

    def search(
            self,
            query: str,
            k: int = 10,
            filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Search for relevant chunks.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Optional metadata filter (e.g., {"language": "python"})

        Returns:
            List of Document objects ordered by relevance
        """
        if filter:
            return self.store.similarity_search(query, k=k, filter=filter)
        return self.store.similarity_search(query, k=k)

    def search_with_scores(
            self,
            query: str,
            k: int = 10,
            filter: dict[str, Any] | None = None,
    ) -> list[tuple[Document, float]]:
        """Search for relevant chunks with similarity scores.

        Args:
            query: Search query text
            k: Number of results to return
            filter: Optional metadata filter

        Returns:
            List of (Document, score) tuples
        """
        if filter:
            return self.store.similarity_search_with_score(query, k=k, filter=filter)
        return self.store.similarity_search_with_score(query, k=k)

    def search_by_language(
            self,
            query: str,
            language: str,
            k: int = 10,
    ) -> list[Document]:
        """Search within a specific programming language.

        Args:
            query: Search query text
            language: Programming language (e.g., "python", "javascript")
            k: Number of results

        Returns:
            List of Document objects
        """
        return self.search(query, k=k, filter={"language": language})

    def search_by_file(
            self,
            query: str,
            path: str,
            k: int = 10,
    ) -> list[Document]:
        """Search within a specific file.

        Args:
            query: Search query text
            path: File path to search within
            k: Number of results

        Returns:
            List of Document objects
        """
        doc_id = self._generate_doc_id(Path(path))
        return self.search(query, k=k, filter={"doc_id": doc_id})

    def build_context(
            self,
            query: str,
            k: int = 5,
            max_chars: int | None = None,
            filter: dict[str, Any] | None = None,
    ) -> str:
        """Build context string for LLM from search results.

        Args:
            query: Search query
            k: Number of chunks to include
            max_chars: Optional character limit
            filter: Optional metadata filter

        Returns:
            Formatted context string
        """
        results = self.search(query, k=k, filter=filter)

        if not results:
            return ""

        context_parts = []
        total_chars = 0

        for doc in results:
            # Build header
            filename = doc.metadata.get("filename", "Unknown")
            chunk_type = doc.metadata.get("chunk_type", "text")
            language = doc.metadata.get("language", "")

            if language:
                header = f"# {filename} [{language}] ({chunk_type})"
            else:
                header = f"# {filename} ({chunk_type})"

            section = f"{header}\n{doc.page_content}"

            # Check character limit
            if max_chars:
                if total_chars + len(section) > max_chars:
                    break
                total_chars += len(section)

            context_parts.append(section)

        return "\n\n---\n\n".join(context_parts)

    def delete_file(self, path: Path | str) -> bool:
        """Remove a file from the index.

        Args:
            path: Path to the file

        Returns:
            True if deleted, False if not found
        """
        doc_id = self._generate_doc_id(Path(path))

        try:
            # Search for all chunks of this document
            results = self.search("", k=10000, filter={"doc_id": doc_id})

            if results:
                # Get IDs from metadata if available
                ids = [doc.metadata.get("chunk_id") for doc in results if doc.metadata.get("chunk_id")]
                if ids:
                    self.store.delete(ids=ids)
                    return True

            return False

        except Exception:
            return False

    def as_retriever(self, **kwargs):
        """Get a LangChain retriever from the store.

        Args:
            **kwargs: Arguments passed to as_retriever()

        Returns:
            VectorStoreRetriever

        Example:
            retriever = indexer.as_retriever(search_kwargs={"k": 5})
        """
        return self.store.as_retriever(**kwargs)

    @staticmethod
    def _generate_doc_id(path: Path) -> str:
        """Generate a deterministic document ID from path."""
        resolved = str(path.resolve())
        return hashlib.sha256(resolved.encode()).hexdigest()[:32]

    @staticmethod
    def _chunks_to_documents(
            chunks: list[Chunk],
            path: Path,
            doc_id: str,
    ) -> list[Document]:
        """Convert chunks to LangChain Documents."""
        indexed_at = datetime.now().isoformat()

        # Get file modification time
        try:
            modified_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        except Exception:
            modified_at = None

        documents = []
        for chunk in chunks:
            metadata = {
                # Document info
                "doc_id": doc_id,
                "chunk_id": chunk.id,
                "path": str(path.resolve()),
                "filename": path.name,
                "extension": path.suffix,

                # Timestamps
                "indexed_at": indexed_at,
                "modified_at": modified_at,

                # Chunk info (filter to primitives for ChromaDB)
                **{k: v for k, v in chunk.metadata.items()
                   if isinstance(v, (str, int, float, bool))},
            }

            documents.append(Document(
                page_content=chunk.content,
                metadata=metadata,
            ))

        return documents

    @staticmethod
    def _elapsed_ms(start_time: datetime) -> float:
        """Calculate elapsed time in milliseconds."""
        return (datetime.now() - start_time).total_seconds() * 1000