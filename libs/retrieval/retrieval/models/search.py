from dataclasses import dataclass
from enum import Enum
from retrieval.models.config import RetrieverConfig


class MatchType(str, Enum):
    """Type of search match."""
    FILENAME = "filename"
    CONTENT = "content"


@dataclass
class SearchRequest:
    query: str
    page: int = 1
    size: int = 10
    config: RetrieverConfig | None = None


@dataclass
class SearchResult:
    path: str
    score: float
    metadata: dict | None = None
    snippet: str | None = None
    line_number: int | None = None
    match_type: MatchType = MatchType.FILENAME


@dataclass
class SearchResponse:
    query: str
    page: int
    size: int
    total: int
    results: list[SearchResult]


