from dataclasses import dataclass


@dataclass
class DaemonStatus:
    """Daemon status information.

    Attributes:
        running: Whether the daemon is running
        pid: Process ID if running
        uptime: Human-readable uptime string
        indexing: Whether indexing is active
        watcher_active: Whether the file watcher is active
        files_indexed: Number of files indexed
    """

    running: bool
    pid: int | None = None
    uptime: str = ""
    indexing: bool = False
    watcher_active: bool = False
    files_indexed: int = 0