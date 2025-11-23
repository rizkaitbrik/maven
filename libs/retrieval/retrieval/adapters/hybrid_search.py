"""Hybrid search adapter combining Spotlight and indexed content search."""

import asyncio
from pathlib import Path
from collections import defaultdict
from retrieval.adapters.spotlight import SpotlightAdapter
from retrieval.adapters.indexed_content_search import IndexedContentSearchAdapter
from retrieval.models.search import SearchRequest, SearchResponse, SearchResult, MatchType
from retrieval.models.config import RetrieverConfig


class HybridSearchAdapter:
    """Combines Spotlight filename search and FTS content search with weighted ranking."""

    def __init__(self, root: Path | None = None, config: RetrieverConfig | None = None):
        """Initialize hybrid search adapter.
        
        Args:
            root: Root directory to search from
            config: Retriever configuration
        """
        self.root = root or Path.home()
        self.config = config or RetrieverConfig()
        
        # Initialize both search adapters
        self.spotlight = SpotlightAdapter(root, config)
        self.content_search = IndexedContentSearchAdapter(root, config)
        
        # Get hybrid search config
        self.hybrid_config = self.config.hybrid_search

    def _merge_results(
        self,
        spotlight_response: SearchResponse,
        content_response: SearchResponse
    ) -> list[SearchResult]:
        """Merge results from both searches with weighted ranking.
        
        Args:
            spotlight_response: Results from Spotlight search
            content_response: Results from content search
            
        Returns:
            Merged and weighted list of results
        """
        # Group results by path
        results_by_path = defaultdict(list)
        
        # Add spotlight results with filename weight
        for result in spotlight_response.results:
            weighted_result = SearchResult(
                path=result.path,
                score=result.score * self.hybrid_config.filename_match_weight,
                snippet=result.snippet,
                line_number=result.line_number,
                match_type=MatchType.FILENAME,
                metadata={
                    **(result.metadata or {}),
                    'original_score': result.score,
                    'weight': self.hybrid_config.filename_match_weight,
                    'source': 'spotlight'
                }
            )
            results_by_path[result.path].append(weighted_result)
        
        # Add content results with content weight
        for result in content_response.results:
            weighted_result = SearchResult(
                path=result.path,
                score=result.score * self.hybrid_config.content_match_weight,
                snippet=result.snippet,
                line_number=result.line_number,
                match_type=MatchType.CONTENT,
                metadata={
                    **(result.metadata or {}),
                    'original_score': result.score,
                    'weight': self.hybrid_config.content_match_weight,
                    'source': 'content'
                }
            )
            results_by_path[result.path].append(weighted_result)
        
        # Merge or deduplicate based on config
        merged_results = []
        
        for path, path_results in results_by_path.items():
            if self.hybrid_config.deduplicate:
                # Keep the highest scoring match
                best_result = max(path_results, key=lambda r: r.score)
                
                # If same file matched in both, combine metadata
                if len(path_results) > 1:
                    sources = [r.metadata.get('source') for r in path_results if r.metadata]
                    match_types = [r.match_type for r in path_results]
                    
                    # Use content snippet if available, otherwise filename
                    snippet = None
                    line_number = None
                    for r in path_results:
                        if r.snippet:
                            snippet = r.snippet
                            line_number = r.line_number
                            break
                    
                    merged_result = SearchResult(
                        path=best_result.path,
                        score=best_result.score,
                        snippet=snippet or best_result.snippet,
                        line_number=line_number or best_result.line_number,
                        match_type=best_result.match_type,
                        metadata={
                            **(best_result.metadata or {}),
                            'matched_in': sources,
                            'match_types': [mt.value for mt in match_types],
                            'combined': True
                        }
                    )
                    merged_results.append(merged_result)
                else:
                    merged_results.append(best_result)
            else:
                # Keep all results (no deduplication)
                merged_results.extend(path_results)
        
        # Sort by weighted score (highest first)
        merged_results.sort(key=lambda r: r.score, reverse=True)
        
        return merged_results

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Perform hybrid search combining Spotlight and content search.
        
        Args:
            request: Search request with query and pagination
            
        Returns:
            SearchResponse with merged, weighted results
        """
        if not self.hybrid_config.enabled:
            # Fall back to spotlight only
            return await self.spotlight.search(request)
        
        # Create requests with no pagination for both searches
        spotlight_request = SearchRequest(
            query=request.query,
            page=1,
            size=1000,  # Get many results before merging
            config=request.config
        )
        
        content_request = SearchRequest(
            query=request.query,
            page=1,
            size=1000,
            config=request.config
        )
        
        # Run both searches in parallel
        try:
            spotlight_response, content_response = await asyncio.gather(
                self.spotlight.search(spotlight_request),
                self.content_search.search(content_request),
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(spotlight_response, Exception):
                print(f"Spotlight search error: {spotlight_response}")
                spotlight_response = SearchResponse(
                    query=request.query, page=1, size=0, total=0, results=[]
                )
            
            if isinstance(content_response, Exception):
                print(f"Content search error: {content_response}")
                content_response = SearchResponse(
                    query=request.query, page=1, size=0, total=0, results=[]
                )
        except Exception as e:
            print(f"Hybrid search error: {e}")
            # Fall back to spotlight only
            return await self.spotlight.search(request)
        
        # Merge and weight results
        merged_results = self._merge_results(spotlight_response, content_response)
        
        # Apply pagination to merged results
        total = len(merged_results)
        offset = (request.page - 1) * request.size
        paginated_results = merged_results[offset:offset + request.size]
        
        return SearchResponse(
            query=request.query,
            page=request.page,
            size=request.size,
            total=total,
            results=paginated_results
        )

    def get_stats(self) -> dict:
        """Get hybrid search statistics.
        
        Returns:
            Dictionary with stats from both search methods
        """
        try:
            content_stats = self.content_search.get_stats()
        except Exception as e:
            content_stats = {"error": str(e)}
        
        return {
            "hybrid_enabled": self.hybrid_config.enabled,
            "filename_weight": self.hybrid_config.filename_match_weight,
            "content_weight": self.hybrid_config.content_match_weight,
            "deduplicate": self.hybrid_config.deduplicate,
            "content_index": content_stats
        }

