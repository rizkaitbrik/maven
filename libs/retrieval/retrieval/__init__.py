"""Maven's retrieval package"""

from retrieval.adapters.content_search import ContentSearchAdapter
from retrieval.adapters.hybrid_search import HybridSearchAdapter
from retrieval.adapters.indexed_content_search import IndexedContentSearchAdapter
from retrieval.adapters.spotlight import SpotlightAdapter
from retrieval.interfaces.retriever import Retriever
from retrieval.models.config import HybridSearchConfig, IndexConfig, RetrieverConfig
from retrieval.models.search import (
    MatchType,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from retrieval.services.background_indexer import BackgroundIndexer
from retrieval.services.config_manager import ConfigManager
from retrieval.services.content_extractor import ContentExtractor, ExtractedContent
from retrieval.services.fs_watcher import FileSystemWatcher
from retrieval.services.index_manager import IndexManager

__all__ = [
    "SpotlightAdapter",
    "ContentSearchAdapter",
    "IndexedContentSearchAdapter",
    "HybridSearchAdapter",
    "Retriever",
    "SearchRequest",
    "SearchResponse",
    "SearchResult",
    "MatchType",
    "RetrieverConfig",
    "IndexConfig",
    "HybridSearchConfig",
    "ConfigManager",
    "ContentExtractor",
    "ExtractedContent",
    "IndexManager",
    "FileSystemWatcher",
    "BackgroundIndexer",
]
