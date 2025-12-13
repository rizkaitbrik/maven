"""Index management actions."""

from pathlib import Path
from typing import Callable

from core.models.actions import ActionResult
from core.models.index import IndexStats


class IndexActions:
    """Encapsulates index management business logic.

    This class provides high-level operations for managing the Maven semantic index.
    """

    def __init__(self, config=None):
        """Initialize index actions.

        Args:
            config: Optional RetrieverConfig instance. If not provided,
                    will load from ConfigManager.
        """
        self._config = config
        self._semantic_indexer = None

    @property
    def config(self):
        """Get configuration, loading if necessary."""
        if self._config is None:
            from retrieval.services.config_manager import ConfigManager

            self._config = ConfigManager().config
        return self._config

    @property
    def semantic_indexer(self):
        """Get semantic indexer, creating if necessary."""
        if self._semantic_indexer is None:
            from indexer.chunking.router import ChunkingRouter
            from indexer.extraction.adapters.code import CodeExtractor
            from indexer.extraction.adapters.text import TextExtractor
            from indexer.extraction.router import ExtractionRouter
            from indexer.indexer import SemanticIndexer
            from langchain_chroma import Chroma

            # 1. Setup routers
            extraction = ExtractionRouter()
            extraction.register(
                TextExtractor(
                    extensions=set(self.config.indexer.extraction.allowed_extensions)
                )
            )
            extraction.register(
                CodeExtractor(
                    extensions=set(self.config.indexer.extraction.allowed_extensions)
                )
            )

            chunking = ChunkingRouter()

            # 2. Setup VectorStore
            provider = self.config.indexer.embedding.provider

            if provider == "openai":
                from langchain_openai import OpenAIEmbeddings

                embedding_function = OpenAIEmbeddings(
                    model=self.config.indexer.embedding.model
                )
            elif provider == "huggingface":
                from langchain_huggingface import HuggingFaceEmbeddings

                embedding_function = HuggingFaceEmbeddings(
                    model_name=self.config.indexer.embedding.model
                )
            elif provider == "ollama":
                from langchain_ollama import OllamaEmbeddings

                embedding_function = OllamaEmbeddings(
                    model=self.config.indexer.embedding.model
                )
            else:
                raise ValueError(f"Unsupported embedding provider: {provider}")

            persist_directory = str(
                Path(self.config.indexer.persist_directory).expanduser()
            )

            store = Chroma(
                collection_name=self.config.indexer.collection_name,
                embedding_function=embedding_function,
                persist_directory=persist_directory,
            )

            self._semantic_indexer = SemanticIndexer(
                extraction_router=extraction,
                chunking_router=chunking,
                store=store,
            )

        return self._semantic_indexer

    @property
    def get_stats(self) -> IndexStats:
        """Get index statistics.

        Returns:
            IndexStats with current index information
        """
        # TODO: Implement accurate stats for Chroma
        # For now, return basic info
        
        file_count = 0
        try:
            if hasattr(self.semantic_indexer.store, "_collection"):
                file_count = self.semantic_indexer.store._collection.count()
        except Exception:
            pass

        return IndexStats(
            file_count=file_count, # This is actually chunk count
            total_size_bytes=0,
            last_indexed_at=None,
            db_path=self.config.indexer.persist_directory,
            watcher_enabled=False,
        )

    def start_indexing(
        self,
        root: Path | None = None,
        rebuild: bool = False,
        progress_callback: Callable[[int, int, str], None] | None = None,
        recursive: bool = True
    ) -> ActionResult:
        """Start indexing files (synchronous for now).

        Args:
            root: Root directory to index (uses config default if not provided)
            rebuild: Whether to rebuild the entire index
            progress_callback: Optional callback for progress updates

        Returns:
            ActionResult indicating success or failure
            :param root:
            :param rebuild:
            :param progress_callback:
            :param recursive:
        """
        indexing_root = Path(root or self.config.root)
        
        if not indexing_root.exists():
             return ActionResult(success=False, message=f"Root directory not found: {indexing_root}")

        try:
            results = self.semantic_indexer.synchronize_directory(
                directory=indexing_root,
                recursive=recursive,
                progress_callback=progress_callback,
                block_list=self.config.block_list,
                force_rebuild=rebuild
            )
            
            success_count = sum(1 for r in results if r.success)
            total_chunks = sum(r.chunk_count for r in results if r.success)
            
            return ActionResult(
                success=True,
                message=f"Indexing completed at {indexing_root}",
                data={
                    "root": str(indexing_root),
                    "rebuild": rebuild,
                    "total_files": len(results),
                    "success_count": success_count,
                    "total_chunks": total_chunks
                },
            )
        except Exception as e:
            return ActionResult(success=False, message=str(e))

    def clear_index(self) -> ActionResult:
        """Clear the entire index.

        Returns:
            ActionResult indicating success or failure
        """
        try:
            success = self.semantic_indexer.clear_index()
            if success:
                return ActionResult(success=True, message="Index cleared")
            return ActionResult(
                success=False, 
                message="Failed to clear index (method not supported by store)"
            )
        except Exception as e:
            return ActionResult(success=False, message=str(e))
    
    @staticmethod
    def get_watcher_status() -> bool:
        """Get file watcher status."""
        return False

    # Keep compatibility methods if needed, but we are moving away from them
    # For semantic_index_file and search, we can expose them if CLI uses them directly
    # But CLI 'index' command now uses start_indexing which maps to sync_directory.

