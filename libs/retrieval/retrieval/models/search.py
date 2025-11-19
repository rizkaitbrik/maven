from dataclasses import dataclass


@dataclass
class SearchRequest:
    query: str
    page: int = 1
    size: int = 10

@dataclass
class SearchResult:
    path: str
    score: float
    metadata: dict | None = None


@dataclass
class SearchResponse:
    query: str
    page: int
    size: int
    total: int
    results: list[SearchResult]


