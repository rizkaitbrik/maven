from typing import Protocol

from retrieval.models.search import SearchRequest, SearchResponse


class Retriever(Protocol):
    async def search(self, request: SearchRequest) -> SearchResponse:
        ...