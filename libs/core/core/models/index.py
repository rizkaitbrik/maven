from dataclasses import dataclass


@dataclass
class IndexStats:
    """Index statistics information.

    Attributes:
        file_count: Number of files in the index
        total_size_bytes: Total size in bytes (approximate)
        last_indexed_at: Timestamp of last indexing
        db_path: Path to the database
        watcher_enabled: Whether the file watcher is enabled
    """

    file_count: int
    total_size_bytes: int
    last_indexed_at: float | None
    db_path: str
    watcher_enabled: bool = False