"""File system watcher for automatic index updates."""

import time
import threading
from pathlib import Path
from typing import Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from retrieval.models.config import RetrieverConfig, IndexConfig
from retrieval.services.index_manager import IndexManager
from maven_logging import get_logger


class DebouncedFileHandler(FileSystemEventHandler):
    """File system event handler with debouncing."""

    def __init__(
            self,
            index_manager: IndexManager,
            config: RetrieverConfig,
            debounce_ms: int
    ):
        """Initialize the handler.
        
        Args:
            index_manager: Index manager to update
            config: Retriever configuration for filtering
            debounce_ms: Debounce delay in milliseconds
        """
        super().__init__()
        self.index_manager = index_manager
        self.config = config
        self.debounce_seconds = debounce_ms / 1000.0
        self.logger = get_logger('retrieval.watcher')

        # Pending changes to process
        self._pending_updates: Set[Path] = set()
        self._pending_deletes: Set[Path] = set()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def _should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed based on config.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file should be processed
        """
        if not file_path.is_file():
            return False

        file_str = str(file_path)

        # Check if blocked
        if self.config.is_blocked(file_str):
            return False

        # Check if allowed
        if not self.config.is_allowed(file_str):
            return False

        # Check if text file
        if not self.index_manager.content_extractor.is_text_file(file_path):
            return False

        return True

    def _schedule_flush(self):
        """Schedule a flush of pending changes."""
        with self._lock:
            if self._timer:
                self._timer.cancel()

            self._timer = threading.Timer(
                self.debounce_seconds,
                self._flush_changes
            )
            self._timer.daemon = True
            self._timer.start()

    def _flush_changes(self):
        """Process all pending changes."""
        with self._lock:
            updates = self._pending_updates.copy()
            deletes = self._pending_deletes.copy()
            self._pending_updates.clear()
            self._pending_deletes.clear()
            self._timer = None

        if updates or deletes:
            self.logger.info("Processing file changes", updates=len(updates), deletes=len(deletes))

        # Process deletions first
        for file_path in deletes:
            if file_path not in updates:  # Don't delete if it's being updated
                try:
                    self.logger.debug("Removing file from index", path=str(file_path))
                    self.index_manager.remove_file(file_path)
                    self.logger.info("File removed from index", path=str(file_path))
                except Exception as e:
                    self.logger.error("Failed to remove file from index", path=str(file_path), error=str(e))

        # Process updates
        for file_path in updates:
            try:
                self.logger.debug("Indexing file", path=str(file_path))
                self.index_manager.add_or_update_file(file_path)
                self.logger.info("File indexed", path=str(file_path))
            except Exception as e:
                self.logger.error("Failed to index file", path=str(file_path), error=str(e))

    def on_created(self, event: FileSystemEvent):
        """Handle file creation."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if self._should_process_file(file_path):
            self.logger.debug("File created", path=str(file_path), action="created")
            with self._lock:
                self._pending_updates.add(file_path)
            self._schedule_flush()

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if self._should_process_file(file_path):
            self.logger.debug("File modified", path=str(file_path), action="modified")
            with self._lock:
                self._pending_updates.add(file_path)
            self._schedule_flush()

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        self.logger.debug("File deleted", path=str(file_path), action="deleted")
        # Always process deletions (can't check if it should be processed since file is gone)
        with self._lock:
            self._pending_deletes.add(file_path)
            # Remove from pending updates if it was there
            self._pending_updates.discard(file_path)
        self._schedule_flush()

    def on_moved(self, event: FileSystemEvent):
        """Handle file move/rename."""
        if event.is_directory:
            return

        # Treat as delete + create
        src_path = Path(event.src_path)
        dest_path = Path(event.dest_path)

        self.logger.debug("File moved", src=str(src_path), dest=str(dest_path), action="moved")

        with self._lock:
            self._pending_deletes.add(src_path)
            if self._should_process_file(dest_path):
                self._pending_updates.add(dest_path)

        self._schedule_flush()


class FileSystemWatcher:
    """Watches file system for changes and updates the index."""

    def __init__(
            self,
            index_manager: IndexManager,
            config: RetrieverConfig
    ):
        """Initialize the file system watcher.
        
        Args:
            index_manager: Index manager to update
            config: Retriever configuration
        """
        self.index_manager = index_manager
        self.config = config
        self.observer: Observer | None = None
        self.handler: DebouncedFileHandler | None = None
        self._running = False
        self.logger = get_logger('retrieval.watcher')

    def start(self, watch_paths: list[Path] | None = None):
        """Start watching for file changes.
        
        Args:
            watch_paths: Paths to watch, defaults to config root
        """
        if self._running:
            return

        if not self.config.index.enable_watcher:
            return

        # Determine paths to watch
        if watch_paths is None:
            if self.config.allowed_list:
                # Watch allowed directories
                watch_paths = []
                for pattern in self.config.allowed_list:
                    # Skip glob patterns, only watch real directories
                    if not any(c in pattern for c in ['*', '?', '[', ']']):
                        path = Path(pattern).expanduser().resolve()
                        if path.exists() and path.is_dir():
                            watch_paths.append(path)

                # If no real directories, watch root
                if not watch_paths:
                    watch_paths = [self.config.root]
            else:
                watch_paths = [self.config.root]

        # Create handler and observer
        self.handler = DebouncedFileHandler(
            self.index_manager,
            self.config,
            self.config.index.debounce_ms
        )

        self.observer = Observer()

        # Schedule watching for each path
        for path in watch_paths:
            if path.exists() and path.is_dir():
                self.logger.info("Watching directory", path=str(path))
                self.observer.schedule(
                    self.handler,
                    str(path),
                    recursive=True
                )

        self.observer.start()
        self._running = True
        self.logger.info("File system watcher started", watch_count=len(watch_paths))

    def stop(self):
        """Stop watching for file changes."""
        if not self._running:
            return

        self.logger.info("Stopping file system watcher")

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5.0)
            self.observer = None

        self.handler = None
        self._running = False
        self.logger.info("File system watcher stopped")

    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running
