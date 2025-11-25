"""Index management actions."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class IndexStats:
    """Index statistics information.

    Attributes:
        file_count: Number of files in the index
        total_size_bytes: Total size in bytes
        last_indexed_at: Timestamp of last indexing
        db_path: Path to the database
        watcher_enabled: Whether the file watcher is enabled
    """

    file_count: int
    total_size_bytes: int
    last_indexed_at: float | None
    db_path: str
    watcher_enabled: bool = False


@dataclass
class ActionResult:
    """Result from an action.

    Attributes:
        success: Whether the action succeeded
        message: Human-readable message about the result
        data: Optional additional data
    """

    success: bool
    message: str
    data: dict | None = None


class IndexActions:
    """Encapsulates index management business logic.

    This class provides high-level operations for managing the Maven index,
    abstracting away the details of index management and background indexing.
    """

    def __init__(self, config=None):
        """Initialize index actions.

        Args:
            config: Optional RetrieverConfig instance. If not provided,
                    will load from ConfigManager.
        """
        self._config = config
        self._index_manager = None
        self._indexer = None

    @property
    def config(self):
        """Get configuration, loading if necessary."""
        if self._config is None:
            from retrieval.services.config_manager import ConfigManager

            self._config = ConfigManager().config
        return self._config

    @property
    def index_manager(self):
        """Get index manager, creating if necessary."""
        if self._index_manager is None:
            from retrieval.services.index_manager import IndexManager

            self._index_manager = IndexManager(
                self.config.index,
                self.config.text_extensions,
            )
        return self._index_manager

    @property
    def indexer(self):
        """Get background indexer, creating if necessary."""
        if self._indexer is None:
            from retrieval.services.background_indexer import BackgroundIndexer

            self._indexer = BackgroundIndexer(
                self.index_manager,
                self.config,
            )
        return self._indexer

    def get_stats(self) -> IndexStats:
        """Get index statistics.

        Returns:
            IndexStats with current index information
        """
        stats = self.index_manager.get_stats()

        return IndexStats(
            file_count=stats.get("file_count", 0),
            total_size_bytes=stats.get("total_size_bytes", 0),
            last_indexed_at=stats.get("last_indexed_at"),
            db_path=stats.get("db_path", ""),
            watcher_enabled=self.config.index.enable_watcher,
        )

    def start_indexing(
        self,
        root: Path | None = None,
        rebuild: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> ActionResult:
        """Start indexing files.

        Args:
            root: Root directory to index (uses config default if not provided)
            rebuild: Whether to rebuild the entire index
            progress_callback: Optional callback for progress updates (current, total)

        Returns:
            ActionResult indicating success or failure
        """
        indexing_root = root or self.config.root

        self.indexer.start_indexing(
            root=indexing_root,
            rebuild=rebuild,
            progress_callback=progress_callback,
        )

        return ActionResult(
            success=True,
            message=f"Indexing started at {indexing_root}",
            data={"root": str(indexing_root), "rebuild": rebuild},
        )

    def stop_indexing(self) -> ActionResult:
        """Stop ongoing indexing.

        Returns:
            ActionResult indicating success or failure
        """
        if not self.indexer.is_indexing():
            return ActionResult(
                success=False,
                message="Indexing is not in progress",
            )

        self.indexer.stop_indexing()

        return ActionResult(
            success=True,
            message="Indexing stopped",
        )

    def wait_for_completion(self, poll_interval: float = 0.1) -> tuple[int, int]:
        """Wait for indexing to complete.

        Args:
            poll_interval: Seconds between progress checks

        Returns:
            Tuple of (files_indexed, total_files)
        """
        import time

        while self.indexer.is_indexing():
            time.sleep(poll_interval)

        return self.indexer.get_progress()

    def is_indexing(self) -> bool:
        """Check if indexing is in progress.

        Returns:
            True if indexing is active
        """
        return self.indexer.is_indexing()

    def get_progress(self) -> tuple[int, int]:
        """Get indexing progress.

        Returns:
            Tuple of (current, total) files
        """
        return self.indexer.get_progress()

    def clear_index(self) -> ActionResult:
        """Clear the entire index.

        Returns:
            ActionResult indicating success or failure
        """
        self.index_manager.clear()

        return ActionResult(
            success=True,
            message="Index cleared",
        )

    def get_watcher_status(self) -> bool:
        """Get file watcher status.

        Returns:
            True if watcher is active
        """
        return self.indexer.get_watcher_status()
