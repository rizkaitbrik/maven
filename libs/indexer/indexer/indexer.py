"""Semantic indexer - orchestrates extraction, chunking, and storage."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

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

    def _process_file(self, path: Path) -> tuple[list[Document], IndexingResult]:
        """Process a single file: extract, chunk, and prepare documents.
        
        Does NOT store in VectorStore.
        """
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
                result = IndexingResult(
                    doc_id=doc_id,
                    path=str(path),
                    chunk_count=0,
                    success=True,
                    duration_ms=self._elapsed_ms(start_time),
                )
                return [], result

            # 4. Prepare documents for LangChain
            documents = self._chunks_to_documents(chunks, path, doc_id)
            
            # Attach explicit chunk IDs to documents for storage
            # (LangChain's add_documents takes ids separately, but we prep here)
            for i, doc in enumerate(documents):
                doc.metadata["chunk_id"] = chunks[i].id

            result = IndexingResult(
                doc_id=doc_id,
                path=str(path),
                chunk_count=len(chunks),
                success=True,
                duration_ms=self._elapsed_ms(start_time),
            )
            return documents, result

        except Exception as e:
            result = IndexingResult(
                doc_id=self._generate_doc_id(path),
                path=str(path),
                chunk_count=0,
                success=False,
                error=str(e),
                duration_ms=self._elapsed_ms(start_time),
            )
            return [], result

    def index_file(self, path: Path | str) -> IndexingResult:
        """Index a single file (upsert).

        Args:
            path: Path to the file

        Returns:
            IndexingResult with status and metadata
        """
        path = Path(path)
        
        # 1. Process file (extract + chunk)
        documents, result = self._process_file(path)
        
        if documents:
            # 2. Delete existing chunks for this file (Upsert logic)
            # We use doc_id from the first document (all have same doc_id)
            doc_id = documents[0].metadata["doc_id"]
            self._delete_by_doc_id(doc_id)
            
            # 3. Add new chunks
            ids = [doc.metadata["chunk_id"] for doc in documents]
            self.store.add_documents(documents, ids=ids)
            
        return result

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

    def synchronize_directory(
            self,
            directory: Path | str,
            recursive: bool = True,
            batch_size: int = 10,
            progress_callback: Callable[[int, int, str], None] | None = None,
            block_list: list[str] | None = None,
            force_rebuild: bool = False,
    ) -> list[IndexingResult]:
        """Synchronize a directory with the index (incremental update).

        Args:
            directory: Directory to sync
            recursive: Whether to search recursively
            batch_size: Batch size for indexing
            progress_callback: Callback(processed_count, total_count, status_message)
            block_list: Patterns to exclude
            force_rebuild: Ignore timestamps and re-index everything

        Returns:
            List of IndexingResult
        """
        directory = Path(directory)
        block_list = block_list or []

        # 1. Scan filesystem for current files
        if recursive:
            files = list(directory.rglob("*"))
        else:
            files = list(directory.glob("*"))

        def is_blocked(path: Path) -> bool:
            import fnmatch
            path_str = str(path)
            for pattern in block_list:
                if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                    return True
                if pattern.startswith("**/") and pattern.endswith("/**"):
                    dirname = pattern[3:-3]
                    if dirname in path.parts:
                        return True
            return False

        current_files = {
            str(f.resolve()): f 
            for f in files 
            if f.is_file() and self.extraction.supports(f) and not is_blocked(f)
        }

        # 2. Get existing index state
        indexed_files = {}  # path -> modified_at
        
        try:
            # Fetch all metadata from Chroma
            # We use the underlying collection directly for efficiency if possible
            if hasattr(self.store, "_collection"):
                result = self.store._collection.get(include=["metadatas"])
                metadatas = result.get("metadatas", [])
                for meta in metadatas:
                    if meta and "path" in meta and "modified_at" in meta:
                        indexed_files[meta["path"]] = meta["modified_at"]
            else:
                # Fallback (slow): might skip this optimization or warn
                pass
        except Exception as e:
            print(f"Warning: Could not fetch existing index state: {e}")

        # 3. Determine work
        to_add = []
        to_update = []
        to_delete = []

        # Check existing files vs current filesystem
        for path_str, timestamp in indexed_files.items():
            if path_str not in current_files:
                to_delete.append(path_str)
            elif not force_rebuild:
                # Check timestamp
                current_file = current_files[path_str]
                try:
                    current_mtime = datetime.fromtimestamp(current_file.stat().st_mtime).isoformat()
                    if current_mtime != timestamp:
                        to_update.append(current_files[path_str])
                except Exception:
                    to_update.append(current_files[path_str])

        # Check new files
        for path_str, path in current_files.items():
            if path_str not in indexed_files:
                to_add.append(path)
            elif force_rebuild:
                 to_update.append(path)

        total_ops = len(to_add) + len(to_update) + len(to_delete)
        processed = 0
        results = []

        if progress_callback:
            progress_callback(0, total_ops, "Starting synchronization...")

        # 4. Execute Deletions
        for path_str in to_delete:
            self.delete_file(path_str)
            processed += 1
            if progress_callback:
                progress_callback(processed, total_ops, f"Deleted {Path(path_str).name}")

        # 5. Execute Updates & Additions (batched)
        files_to_index = to_add + to_update
        
        for i in range(0, len(files_to_index), batch_size):
            batch_paths = files_to_index[i : i + batch_size]
            batch_documents = []
            batch_ids = []
            
            for path in batch_paths:
                # Remove old chunks if updating
                if path in to_update or force_rebuild:
                     # Since we do batched add at the end, we should delete first
                     # But _process_file doesn't interact with DB.
                     # index_file does both. 
                     # We should replicate batch logic from index_directory but with upsert awareness.
                     
                     # First delete existing (if any)
                     doc_id = self._generate_doc_id(path)
                     self._delete_by_doc_id(doc_id)

                documents, result = self._process_file(path)
                results.append(result)
                
                if documents:
                    batch_documents.extend(documents)
                    batch_ids.extend([doc.metadata["chunk_id"] for doc in documents])
            
            if batch_documents:
                self.store.add_documents(batch_documents, ids=batch_ids)
            
            processed += len(batch_paths)
            if progress_callback:
                current_file_name = batch_paths[-1].name if batch_paths else ""
                progress_callback(processed, total_ops, f"Indexed {current_file_name}")

        return results

    def index_directory(
            self,
            directory: Path | str,
            recursive: bool = True,
            batch_size: int = 10,
            progress_callback: Callable[[int, int], None] | None = None,
            block_list: list[str] | None = None,
    ) -> list[IndexingResult]:
        """Index all supported files in a directory.

        Args:
            directory: Directory path
            recursive: Whether to search recursively
            batch_size: Number of files to process in a batch before writing to DB
            progress_callback: Callback receiving (processed_count, total_count)
            block_list: List of patterns to exclude (glob patterns)

        Returns:
            List of IndexingResult for each file
        """
        directory = Path(directory)
        block_list = block_list or []

        if recursive:
            files = list(directory.rglob("*"))
        else:
            files = list(directory.glob("*"))

        def is_blocked(path: Path) -> bool:
            import fnmatch
            path_str = str(path)
            for pattern in block_list:
                if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                    return True
                # Handle directory matching (e.g. **/node_modules/**)
                if pattern.startswith("**/") and pattern.endswith("/**"):
                    dirname = pattern[3:-3]
                    if dirname in path.parts:
                        return True
            return False

        # Filter to supported files only and exclude blocked paths
        supported_files = [
            f for f in files
            if f.is_file() 
            and self.extraction.supports(f)
            and not is_blocked(f)
        ]
        
        total_files = len(supported_files)
        results = []
        processed_count = 0
        
        if progress_callback:
            progress_callback(0, total_files)

        # Process in batches
        for i in range(0, total_files, batch_size):
            batch_paths = supported_files[i : i + batch_size]
            batch_documents = []
            batch_ids = []
            
            for path in batch_paths:
                documents, result = self._process_file(path)
                results.append(result)
                
                if documents:
                    batch_documents.extend(documents)
                    batch_ids.extend([doc.metadata["chunk_id"] for doc in documents])
            
            # Batch write to store (IO/GPU heavy)
            if batch_documents:
                self.store.add_documents(batch_documents, ids=batch_ids)
            
            processed_count += len(batch_paths)
            if progress_callback:
                progress_callback(processed_count, total_files)

        return results

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

    def _delete_by_doc_id(self, doc_id: str) -> bool:
        """Delete all chunks for a document ID."""
        try:
            # Try efficient delete via metadata filter if supported by store
            if hasattr(self.store, "_collection"):
                try:
                    self.store._collection.delete(where={"doc_id": doc_id})
                    return True
                except Exception:
                    pass

            # Fallback: Search and delete by IDs
            # Note: We use a large limit to catch all chunks
            results = self.store.similarity_search("", k=1000, filter={"doc_id": doc_id})
            if results:
                ids = [doc.metadata.get("chunk_id") for doc in results if doc.metadata.get("chunk_id")]
                if ids:
                    self.store.delete(ids=ids)
                    return True
            return False
        except Exception:
            return False

    def delete_file(self, path: Path | str) -> bool:
        """Remove a file from the index.

        Args:
            path: Path to the file

        Returns:
            True if deleted, False if not found
        """
        doc_id = self._generate_doc_id(Path(path))
        return self._delete_by_doc_id(doc_id)

    def clear_index(self) -> bool:
        """Clear the entire index.

        Returns:
            True if successful
        """
        try:
            # Method 1: Delete collection (fastest)
            if hasattr(self.store, "delete_collection"):
                self.store.delete_collection()
                return True
            
            # Method 2: Access underlying client to delete collection
            if hasattr(self.store, "_collection"):
                try:
                    self.store._collection.delete()
                    return True
                except Exception:
                    pass

            # Method 3: Delete by IDs (fallback)
            # This is slow for large collections but most compatible
            try:
                # Retrieve all IDs. 
                # Note: Chroma's get() returns all IDs if no limit is specified (or limit is large)
                # We fetch just IDs to be efficient
                # langchain-chroma's get() might return a dict or list depending on version
                result = self.store.get()
                
                ids = []
                if isinstance(result, dict):
                    ids = result.get("ids", [])
                elif hasattr(result, "ids"): # Some result objects
                    ids = result.ids
                
                if ids:
                    self.store.delete(ids=ids)
                return True
            except Exception:
                pass
                
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
