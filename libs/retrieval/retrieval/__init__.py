"""Maven's retrieval package"""

from retrieval.adapters.spotlight import SpotlightAdapter
from retrieval.adapters.content_search import ContentSearchAdapter
from retrieval.interfaces.retriever import Retriever
from retrieval.models.search import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    MatchType,
)
from retrieval.models.config import RetrieverConfig
from retrieval.services.config_manager import ConfigManager
from retrieval.services.content_extractor import ContentExtractor, ExtractedContent

__all__ = [
    "SpotlightAdapter",
    "ContentSearchAdapter",
    "Retriever",
    "SearchRequest",
    "SearchResponse",
    "SearchResult",
    "MatchType",
    "RetrieverConfig",
    "ConfigManager",
    "ContentExtractor",
    "ExtractedContent",
]
