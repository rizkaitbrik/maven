from dataclasses import dataclass
from enum import Enum


class SearchType(str, Enum):
    """Type of search to perform."""
    FILENAME = "filename"
    CONTENT = "content"
    HYBRID = "hybrid"


@dataclass
class SearchResult:
    """Single search result.

    Attributes:
        path: Path to the matched file
        score: Relevance score
        snippet: Optional content snippet
        line_number: Optional line number for content matches
        match_type: Type of match (filename, content, or both)
        metadata: Additional metadata (AST, etc.)
    """

    path: str
    score: float
    snippet: str | None = None
    line_number: int | None = None
    match_type: str | None = None
    metadata: dict | None = None


@dataclass
class SearchResponse:
    """Search response with results and pagination.

    Attributes:
        query: Original search query
        results: List of search results
        total: Total number of matches
        page: Current page number
        size: Page size
        search_type: Type of search performed
    """

    query: str
    results: list[SearchResult]
    total: int
    page: int
    size: int
    search_type: SearchType = SearchType.FILENAME