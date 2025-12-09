from dataclasses import dataclass


@dataclass
class IndexingResult:
    """Result of indexing a file."""

    doc_id: str
    path: str
    chunk_count: int
    success: bool
    error: str | None = None
    duration_ms: float | None = None
