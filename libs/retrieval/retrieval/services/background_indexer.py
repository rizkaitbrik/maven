"""Background indexing service for initial index creation and updates."""

import threading
from pathlib import Path
from typing import Callable

from maven_logging import get_logger

from retrieval.models.config import RetrieverConfig
from retrieval.services.fs_watcher import FileSystemWatcher
from retrieval.services.index_manager import IndexManager


class BackgroundIndexer:
    """Manages background indexing of files."""

    def __init__(
        self,
        index_manager: IndexManager,
        config: RetrieverConfig
    ):
        """Initialize the background indexer.
        
        Args:
            index_manager: Index manager to use
            config: Retriever configuration
        """
        self.index_manager = index_manager
        self.config = config
        self.fs_watcher: FileSystemWatcher | None = None
        self._indexing_thread: threading.Thread | None = None
        self._is_indexing = False
        self._indexed_count = 0
        self._total_count = 0
        self._progress_callback: Callable[[int, int], None] | None = None
        self.logger = get_logger('retrieval.indexer')

    def _get_indexable_files(self, root: Path) -> list[Path]:
        """Get list of files that should be indexed.
        
        Args:
            root: Root directory to scan
            
        Returns:
            List of file paths to index
        """
        files = []
        
        # Determine directories to scan
        if self.config.allowed_list:
            scan_dirs = []
            for pattern in self.config.allowed_list:
                # Skip glob patterns, only scan real directories
                if not any(c in pattern for c in ['*', '?', '[', ']']):
                    path = Path(pattern).expanduser().resolve()
                    if path.exists() and path.is_dir():
                        scan_dirs.append(path)
            
            if not scan_dirs:
                scan_dirs = [root]
        else:
            scan_dirs = [root]
        
        # Walk directories
        for scan_dir in scan_dirs:
            try:
                for item in scan_dir.rglob('*'):
                    if not item.is_file():
                        continue
                    
                    item_str = str(item)
                    
                    # Apply filtering
                    if self.config.is_blocked(item_str):
                        continue
                    
                    if not self.config.is_allowed(item_str):
                        continue
                    
                    if not self.index_manager.content_extractor.is_text_file(item):
                        continue
                    
                    files.append(item)
            except (PermissionError, OSError):
                # Skip directories we can't access
                continue
        
        return files

    def _index_files(self, files: list[Path]):
        """Index a list of files.
        
        Args:
            files: List of file paths to index
        """
        self._is_indexing = True
        self._indexed_count = 0
        self._total_count = len(files)
        
        self.logger.info("Starting indexing", total_files=self._total_count)
        
        try:
            for i, file_path in enumerate(files):
                if not self._is_indexing:
                    # Indexing was cancelled
                    self.logger.warning(
                        "Indexing cancelled",
                        indexed=self._indexed_count,
                        total=self._total_count
                    )
                    break
                
                try:
                    # Check if file needs indexing
                    if self.index_manager.needs_reindex(file_path):
                        self.index_manager.add_or_update_file(file_path)
                        self._indexed_count += 1
                        progress = f"{i+1}/{self._total_count}"
                        self.logger.debug(
                            "File indexed",
                            path=str(file_path),
                            progress=progress
                        )
                except Exception as e:
                    self.logger.error(
                        "Failed to index file",
                        path=str(file_path),
                        error=str(e)
                    )
                
                # Report progress
                if self._progress_callback and (i + 1) % 10 == 0:
                    self._progress_callback(i + 1, self._total_count)
                
                # Log progress every 100 files
                if (i + 1) % 100 == 0:
                    self.logger.info(
                        "Indexing progress",
                        indexed=self._indexed_count,
                        scanned=i+1,
                        total=self._total_count
                    )
            
            # Final progress update
            if self._progress_callback:
                self._progress_callback(self._total_count, self._total_count)
            
            self.logger.info(
                "Indexing completed",
                indexed=self._indexed_count,
                scanned=len(files),
                total=self._total_count
            )
            
            # Start file system watcher after indexing completes
            if self._is_indexing and self.config.index.enable_watcher:
                self._start_watcher()
        
        finally:
            self._is_indexing = False

    def _start_watcher(self):
        """Start the file system watcher."""
        if self.fs_watcher is None:
            self.fs_watcher = FileSystemWatcher(
                self.index_manager,
                self.config
            )
        
        if not self.fs_watcher.is_running():
            self.logger.info("Starting file system watcher after indexing")
            self.fs_watcher.start()

    def start_indexing(
        self,
        root: Path | None = None,
        rebuild: bool = False,
        progress_callback: Callable[[int, int], None] | None = None
    ):
        """Start indexing in the background.
        
        Args:
            root: Root directory to index (defaults to config root)
            rebuild: Whether to rebuild the entire index
            progress_callback: Optional callback(current, total) for progress updates
        """
        if self._is_indexing:
            self.logger.warning("Indexing already in progress")
            return
        
        root = root or self.config.root
        self._progress_callback = progress_callback
        
        self.logger.info("Preparing to index", root=str(root), rebuild=rebuild)
        
        # Clear index if rebuilding
        if rebuild:
            self.logger.info("Rebuilding index, clearing existing entries")
            self.index_manager.clear()
        
        # Get files to index
        self.logger.info("Scanning for indexable files", root=str(root))
        files = self._get_indexable_files(root)
        self.logger.info("Found indexable files", count=len(files))
        
        # Start indexing in background thread
        self._indexing_thread = threading.Thread(
            target=self._index_files,
            args=(files,),
            daemon=True
        )
        self._indexing_thread.start()
        self.logger.info("Background indexing started")

    def stop_indexing(self):
        """Stop any in-progress indexing."""
        if self._is_indexing:
            self.logger.info("Stopping indexing")
        self._is_indexing = False
        
        if self._indexing_thread:
            self._indexing_thread.join(timeout=5.0)
            self._indexing_thread = None
            self.logger.info("Indexing stopped")

    def stop_watcher(self):
        """Stop the file system watcher."""
        if self.fs_watcher:
            self.logger.info("Stopping file system watcher")
            self.fs_watcher.stop()
            self.fs_watcher = None

    def is_indexing(self) -> bool:
        """Check if indexing is in progress."""
        return self._is_indexing

    def get_progress(self) -> tuple[int, int]:
        """Get current indexing progress.
        
        Returns:
            Tuple of (indexed_count, total_count)
        """
        return (self._indexed_count, self._total_count)

    def get_watcher_status(self) -> bool:
        """Check if file system watcher is running."""
        return self.fs_watcher is not None and self.fs_watcher.is_running()

