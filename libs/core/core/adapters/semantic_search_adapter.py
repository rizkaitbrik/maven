"""Semantic search adapter using ChromaDB."""

from retrieval.interfaces.retriever import Retriever
from retrieval.models.search import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    MatchType,
)
from indexer.indexer import SemanticIndexer


class SemanticSearchAdapter:
    """Search adapter using semantic search (embeddings)."""

    def __init__(self, indexer: SemanticIndexer):
        """Initialize semantic search adapter.

        Args:
            indexer: Configured SemanticIndexer instance
        """
        self.indexer = indexer

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Perform semantic search.

        Args:
            request: Search request

        Returns:
            SearchResponse with results
        """
        # Search using the indexer
        # Note: request.size is mapped to k
        try:
            results_with_scores = self.indexer.search_with_scores(
                query=request.query,
                k=request.size,
                filter=None  # We could add filter support from request.config if needed
            )
        except Exception as e:
            # Return empty response on error
            print(f"Semantic search error: {e}")
            return SearchResponse(
                query=request.query,
                page=request.page,
                size=request.size,
                total=0,
                results=[],
            )

        # Convert to SearchResult objects
        search_results = []
        for doc, score in results_with_scores:
            metadata = doc.metadata or {}
            
            # Extract useful metadata
            path = metadata.get("path", "")
            filename = metadata.get("filename", "")
            chunk_type = metadata.get("chunk_type", "text")
            language = metadata.get("language", "")
            
            # Format snippet for display
            # We might want to include the AST context in the snippet or metadata
            snippet = doc.page_content
            
            # Normalize score (Chroma returns L2 distance by default)
            # Distance: 0 = exact match, higher = more different
            # Similarity: 1 = exact match, 0 = different
            # Convert L2 distance to similarity score: 1 / (1 + distance)
            # This ensures normalized score is always between 0 and 1, with 1 being best.
            similarity_score = 1.0 / (1.0 + score)
            
            search_results.append(
                SearchResult(
                    path=path,
                    score=similarity_score,
                    snippet=snippet,
                    line_number=None, # We don't track line numbers in chunks perfectly yet
                    match_type=MatchType.CONTENT,
                    metadata={
                        **metadata,
                        "ast_context": f"[{language}] {chunk_type}",
                    }
                )
            )

        return SearchResponse(
            query=request.query,
            page=request.page,
            size=request.size,
            total=len(search_results), # This is only 'k' results, not total matches
            results=search_results,
        )
