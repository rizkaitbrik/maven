"""Content search adapter using SQLite FTS index."""

from pathlib import Path
from retrieval.interfaces.retriever import Retriever
from retrieval.models.search import SearchRequest, SearchResponse, SearchResult, MatchType
from retrieval.models.config import RetrieverConfig
from retrieval.services.index_manager import IndexManager


class IndexedContentSearchAdapter:
    """Fast content search using SQLite FTS5 index."""

    def __init__(self, root: Path | None = None, config: RetrieverConfig | None = None):
        """Initialize indexed content search adapter.
        
        Args:
            root: Root directory to search from
            config: Retriever configuration
        """
        self.root = root or Path.home()
        self.config = config or RetrieverConfig()
        
        # Initialize index manager
        self.index_manager = IndexManager(
            self.config.index,
            self.config.text_extensions
        )

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Search indexed content for the given query.
        
        Args:
            request: Search request with query and pagination
            
        Returns:
            SearchResponse with matching results
        """
        # Query the index
        try:
            matches = self.index_manager.search(request.query, limit=10000)
        except Exception as e:
            # If index query fails, return empty results
            print(f"Index search error: {e}")
            matches = []
        
        # Apply pagination
        total = len(matches)
        offset = (request.page - 1) * request.size
        paginated_matches = matches[offset:offset + request.size]
        
        # Convert to SearchResults
        results = []
        for i, match in enumerate(paginated_matches):
            # Calculate score based on rank and position
            # Lower rank (from FTS5) = better match
            # Normalize to 0-1 scale
            if total > 0:
                position_score = 1.0 - (offset + i) / total
                rank_score = 1.0 / (1.0 + match.rank)  # Convert rank to score
                score = (position_score + rank_score) / 2
            else:
                score = 1.0
            
            # Extract line number from snippet if possible
            line_number = None
            snippet = match.snippet
            
            # Try to find line number from file content
            try:
                file_path = Path(match.path)
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                        # Find the approximate line number
                        snippet_text = snippet.replace('→ ', '').replace('...', '').strip()
                        if snippet_text:
                            lines = content.splitlines()
                            for i, line in enumerate(lines, start=1):
                                if snippet_text[:30] in line:
                                    line_number = i
                                    break
            except Exception:
                pass
            
            results.append(SearchResult(
                path=match.path,
                score=score,
                snippet=snippet,
                line_number=line_number,
                match_type=MatchType.CONTENT,
                metadata={
                    'indexed': True,
                    'fts_rank': match.rank
                }
            ))
        
        return SearchResponse(
            query=request.query,
            page=request.page,
            size=request.size,
            total=total,
            results=results
        )

    def get_stats(self) -> dict:
        """Get index statistics.
        
        Returns:
            Dictionary with index stats
        """
        return self.index_manager.get_stats()

