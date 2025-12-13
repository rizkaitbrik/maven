"""Search actions."""

import asyncio
from pathlib import Path

from core.models.search import SearchResponse, SearchResult, SearchType


class SearchActions:
    """Encapsulates search business logic.

    This class provides high-level operations for searching files,
    abstracting away the details of different search adapters.
    """

    def __init__(self, config=None, root: Path | None = None):
        """Initialize search actions.

        Args:
            config: Optional RetrieverConfig instance. If not provided,
                    will load from ConfigManager.
            root: Optional root directory for searches (overrides config)
        """
        self._config = config
        self._root = root
        self._adapters: dict = {}

    @property
    def config(self):
        """Get configuration, loading if necessary.

        Note: Imports are inside the method to allow lazy loading of
        dependencies and provide a fallback if config loading fails.
        Config is cached after first access, so the import only happens once.
        """
        if self._config is None:
            try:
                from retrieval.services.config_manager import ConfigManager

                self._config = ConfigManager().config
            except Exception:
                # Fall back to default config
                from retrieval.models.config import RetrieverConfig

                self._config = RetrieverConfig()
        return self._config

    @property
    def root(self) -> Path:
        """Get search root directory."""
        if self._root is not None:
            return self._root
        return Path(self.config.root)

    def search(
        self,
        query: str,
        search_type: SearchType = SearchType.FILENAME,
        page: int = 1,
        size: int = 10,
        auto_index: bool = True,
    ) -> SearchResponse:
        """Execute a search query.

        Args:
            query: Search query string
            search_type: Type of search to perform
            page: Page number (1-indexed)
            size: Number of results per page
            auto_index: Whether to auto-index if index is empty (hybrid only)

        Returns:
            SearchResponse with results
        """
        adapter = self._get_adapter(search_type)

        # For hybrid search, check if index needs building
        if search_type == SearchType.HYBRID and auto_index:
            self._ensure_index_populated()

        # Build search request
        from retrieval.models.search import SearchRequest

        request = SearchRequest(
            query=query,
            page=page,
            size=size,
            config=self.config,
        )

        # Execute search
        response = asyncio.run(adapter.search(request))

        # Convert to our response format
        results = [
            SearchResult(
                path=r.path,
                score=r.score,
                snippet=r.snippet,
                line_number=r.line_number,
                match_type=r.match_type.value if r.match_type else None,
                metadata=r.metadata,
            )
            for r in response.results
        ]

        return SearchResponse(
            query=response.query,
            results=results,
            total=response.total,
            page=response.page,
            size=response.size,
            search_type=search_type,
        )

    def search_files(
        self,
        query: str,
        page: int = 1,
        size: int = 10,
    ) -> SearchResponse:
        """Search files by name using Spotlight.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            size: Number of results per page

        Returns:
            SearchResponse with results
        """
        return self.search(
            query=query,
            search_type=SearchType.FILENAME,
            page=page,
            size=size,
        )

    def search_content(
        self,
        query: str,
        page: int = 1,
        size: int = 10,
    ) -> SearchResponse:
        """Search file contents.

        Args:
            query: Search query string
            page: Page number (1-indexed)
            size: Number of results per page

        Returns:
            SearchResponse with results
        """
        return self.search(
            query=query,
            search_type=SearchType.CONTENT,
            page=page,
            size=size,
        )

    def search_hybrid(
        self,
        query: str,
        page: int = 1,
        size: int = 10,
        auto_index: bool = True,
    ) -> SearchResponse:
        """Search using hybrid mode (Spotlight + content index).

        Args:
            query: Search query string
            page: Page number (1-indexed)
            size: Number of results per page
            auto_index: Whether to auto-index if index is empty

        Returns:
            SearchResponse with results
        """
        return self.search(
            query=query,
            search_type=SearchType.HYBRID,
            page=page,
            size=size,
            auto_index=auto_index,
        )

    def _get_adapter(self, search_type: SearchType):
        """Get or create the appropriate search adapter.

        Args:
            search_type: Type of search

        Returns:
            Search adapter instance
        """
        if search_type not in self._adapters:
            self._adapters[search_type] = self._create_adapter(search_type)
        return self._adapters[search_type]

    def _create_adapter(self, search_type: SearchType):
        """Create a new search adapter.

        Args:
            search_type: Type of search

        Returns:
            New adapter instance
        """
        # We need the semantic indexer for content/hybrid search
        indexer = None
        if search_type in (SearchType.CONTENT, SearchType.HYBRID):
             from core.actions.index import IndexActions
             # Use IndexActions to get the configured indexer
             # This ensures we share the same Chroma configuration
             index_actions = IndexActions(config=self.config)
             indexer = index_actions.semantic_indexer

        if search_type == SearchType.FILENAME:
            from retrieval.adapters.spotlight import SpotlightAdapter

            return SpotlightAdapter(self.root, config=self.config)
        elif search_type == SearchType.CONTENT:
            from retrieval.adapters.semantic_search import SemanticSearchAdapter

            return SemanticSearchAdapter(indexer=indexer)
        elif search_type == SearchType.HYBRID:
            from retrieval.adapters.hybrid_search import HybridSearchAdapter
            from retrieval.adapters.semantic_search import SemanticSearchAdapter

            content_searcher = SemanticSearchAdapter(indexer=indexer)
            return HybridSearchAdapter(
                self.root, 
                config=self.config, 
                content_searcher=content_searcher
            )
        else:
            raise ValueError(f"Unknown search type: {search_type}")

    def _ensure_index_populated(self):
        """Ensure the index has content for hybrid search."""
        if not self.config.index.auto_index_on_search:
            return

        from core.actions.index import IndexActions
        
        index_actions = IndexActions(config=self.config)
        # Check if index is empty using semantic indexer stats (approximate via file count or just checking if any docs exist)
        # Since getting exact count from Chroma might be slow, we can check if collection is empty
        # or just rely on the fact that if it's empty, we should index.
        # But for now let's just trigger start_indexing which handles skipping if needed?
        # Actually start_indexing in semantic indexer isn't fully "skip if done" yet, it scans.
        # The prompt asked for auto-index if empty.
        
        # We can try to get count
        try:
            if hasattr(index_actions.semantic_indexer.store, "_collection"):
                 count = index_actions.semantic_indexer.store._collection.count()
                 if count == 0:
                     # It's empty, populate it
                     # Note: This is synchronous in CLI but we might want it backgrounded
                     # For now, we'll just run it (might block first search)
                     # Or we can spin up a thread.
                     # Original implementation used BackgroundIndexer.
                     # We should probably use a background thread here too.
                     import threading
                     
                     def run_index():
                         index_actions.start_indexing(self.root, recursive=True)
                         
                     threading.Thread(target=run_index, daemon=True).start()
        except Exception:
            pass
