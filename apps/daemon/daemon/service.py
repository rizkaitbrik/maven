"""Maven daemon core service."""

import os
import signal
import threading
from pathlib import Path
from retrieval.models.config import RetrieverConfig
from retrieval.services.index_manager import IndexManager
from retrieval.services.fs_watcher import FileSystemWatcher
from retrieval.services.background_indexer import BackgroundIndexer
from daemon.state import DaemonStateManager
from maven_logging import get_logger


class MavenDaemon:
    """Maven background daemon service."""

    def __init__(self, config: RetrieverConfig):
        """Initialize the daemon.
        
        Args:
            config: Retriever configuration
        """
        self.config = config
        self.logger = get_logger(
            'daemon',
            log_dir=Path(config.logging.log_dir).expanduser(),
            level=config.logging.level,
            max_file_size=config.logging.max_file_size,
            backup_count=config.logging.backup_count,
            enable_syslog=config.logging.enable_syslog,
            enable_console=config.logging.enable_console
        )

        # State management
        state_dir = Path(config.daemon.state_dir).expanduser()
        self.state_manager = DaemonStateManager(state_dir)

        # Components (initialized in start())
        self.index_manager: IndexManager | None = None
        self.fs_watcher: FileSystemWatcher | None = None
        self.indexer: BackgroundIndexer | None = None

        # Shutdown event
        self._shutdown_event = threading.Event()
        self._running = False

    def start(self):
        """Start the daemon."""
        # Check if already running
        if self.state_manager.is_running():
            raise RuntimeError(f"Daemon already running (PID: {self.state_manager.get_pid()})")

        self.logger.info("Starting Maven daemon", pid=os.getpid())

        # Write PID file
        self.state_manager.write_pid()
        self._running = True

        # Initialize components
        self.index_manager = IndexManager(
            self.config.index,
            self.config.text_extensions
        )

        self.fs_watcher = FileSystemWatcher(
            self.index_manager,
            self.config
        )

        self.indexer = BackgroundIndexer(
            self.index_manager,
            self.config
        )

        # Start file system watcher
        if self.config.index.enable_watcher:
            self.fs_watcher.start()
            self.state_manager.set_watcher_active(True)
            self.logger.info("File system watcher started")

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self.logger.info("Daemon started successfully")

    def stop(self):
        """Stop the daemon gracefully."""
        if not self._running:
            return

        self.logger.info("Stopping Maven daemon")

        # Stop indexer
        if self.indexer:
            self.indexer.stop_indexing()
            self.indexer.stop_watcher()

        # Stop file system watcher
        if self.fs_watcher:
            self.fs_watcher.stop()
            self.state_manager.set_watcher_active(False)

        # Update state
        self.state_manager.remove_pid()
        self._running = False
        self._shutdown_event.set()

        self.logger.info("Daemon stopped")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals.
        
        Args:
            signum: Signal number
            frame: Stack frame
        """
        self.logger.info("Received signal", signal=signum)
        self.stop()

    def wait(self):
        """Wait for daemon to shut down."""
        self._shutdown_event.wait()

    def is_running(self) -> bool:
        """Check if daemon is running.
        
        Returns:
            True if running
        """
        return self._running

    def start_indexing(self, root: Path | None = None, rebuild: bool = False) -> bool:
        """Start indexing.
        
        Args:
            root: Root directory to index
            rebuild: Whether to rebuild the entire index
            
        Returns:
            True if indexing started
        """
        if not self.indexer:
            return False

        if self.indexer.is_indexing():
            self.logger.warning("Indexing already in progress")
            return False

        self.logger.info("Starting indexing", root=str(root), rebuild=rebuild)
        self.state_manager.set_indexing(True)

        def on_progress(current: int, total: int):
            self.state_manager.set_files_indexed(current)

        self.indexer.start_indexing(
            root=root or self.config.root,
            rebuild=rebuild,
            progress_callback=on_progress
        )

        return True

    def stop_indexing(self) -> bool:
        """Stop indexing.
        
        Returns:
            True if indexing stopped
        """
        if not self.indexer:
            return False

        if not self.indexer.is_indexing():
            return False

        self.logger.info("Stopping indexing")
        self.indexer.stop_indexing()
        self.state_manager.set_indexing(False)

        return True

    def get_status(self) -> dict:
        """Get daemon status.
        
        Returns:
            Status dictionary
        """
        status = self.state_manager.get_status()

        # Add current state
        if self.indexer:
            status['indexing'] = self.indexer.is_indexing()
            if status['indexing']:
                current, total = self.indexer.get_progress()
                status['indexing_progress'] = {
                    'current': current,
                    'total': total
                }

        if self.fs_watcher:
            status['watcher_active'] = self.fs_watcher.is_running()

        return status

    def get_index_stats(self) -> dict:
        """Get index statistics.
        
        Returns:
            Index stats dictionary
        """
        if not self.index_manager:
            return {}

        return self.index_manager.get_stats()
