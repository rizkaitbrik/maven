"""Unit tests for search actions."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.actions.search import (
    SearchActions,
    SearchResponse,
    SearchResult,
    SearchType,
)


class TestSearchType:
    """Tests for SearchType enum."""

    def test_enum_values(self):
        """Test enum values."""
        assert SearchType.FILENAME.value == "filename"
        assert SearchType.CONTENT.value == "content"
        assert SearchType.HYBRID.value == "hybrid"


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_minimal_result(self):
        """Test minimal search result."""
        result = SearchResult(
            path="/home/user/file.txt",
            score=0.95,
        )

        assert result.path == "/home/user/file.txt"
        assert result.score == 0.95
        assert result.snippet is None
        assert result.line_number is None
        assert result.match_type is None

    def test_full_result(self):
        """Test search result with all fields."""
        result = SearchResult(
            path="/home/user/code.py",
            score=0.87,
            snippet="def hello_world():",
            line_number=42,
            match_type="content",
        )

        assert result.path == "/home/user/code.py"
        assert result.snippet == "def hello_world():"
        assert result.line_number == 42
        assert result.match_type == "content"


class TestSearchResponse:
    """Tests for SearchResponse dataclass."""

    def test_default_search_type(self):
        """Test default search type."""
        response = SearchResponse(
            query="test",
            results=[],
            total=0,
            page=1,
            size=10,
        )

        assert response.search_type == SearchType.FILENAME

    def test_with_results(self):
        """Test response with results."""
        results = [
            SearchResult(path="/file1.txt", score=0.9),
            SearchResult(path="/file2.txt", score=0.8),
        ]

        response = SearchResponse(
            query="test query",
            results=results,
            total=100,
            page=1,
            size=10,
            search_type=SearchType.CONTENT,
        )

        assert response.query == "test query"
        assert len(response.results) == 2
        assert response.total == 100
        assert response.search_type == SearchType.CONTENT


class TestSearchActions:
    """Tests for SearchActions class."""

    def test_config_lazy_loading(self):
        """Test that config is lazily loaded."""
        with patch(
            "retrieval.services.config_manager.ConfigManager"
        ) as mock_config_manager:
            mock_config = MagicMock()
            mock_config_manager.return_value.config = mock_config

            actions = SearchActions()

            # Config should not be loaded yet
            assert actions._config is None

            # Access config to trigger loading
            config = actions.config

            assert config is mock_config

    def test_config_custom(self):
        """Test using custom config."""
        mock_config = MagicMock()
        actions = SearchActions(config=mock_config)

        assert actions.config is mock_config

    def test_root_override(self):
        """Test root directory override."""
        mock_config = MagicMock()
        mock_config.root = Path("/default/root")

        custom_root = Path("/custom/root")
        actions = SearchActions(config=mock_config, root=custom_root)

        assert actions.root == custom_root

    def test_root_from_config(self):
        """Test root from config when not overridden."""
        mock_config = MagicMock()
        mock_config.root = Path("/config/root")

        actions = SearchActions(config=mock_config)

        assert actions.root == Path("/config/root")

    def test_search_files(self):
        """Test filename search."""
        with patch(
            "retrieval.adapters.spotlight.SpotlightAdapter"
        ) as mock_adapter_class:
            mock_config = MagicMock()
            mock_config.root = Path("/test")

            # Create mock response
            mock_response = MagicMock()
            mock_response.query = "test"
            mock_response.results = [
                MagicMock(
                    path="/test/file.txt",
                    score=0.9,
                    snippet=None,
                    line_number=None,
                    match_type=None,
                )
            ]
            mock_response.total = 1
            mock_response.page = 1
            mock_response.size = 10

            # Create async mock
            mock_adapter = MagicMock()
            mock_adapter.search = AsyncMock(return_value=mock_response)
            mock_adapter_class.return_value = mock_adapter

            actions = SearchActions(config=mock_config)
            response = actions.search_files("test")

            assert response.query == "test"
            assert len(response.results) == 1
            assert response.search_type == SearchType.FILENAME

    def test_search_content(self):
        """Test content search."""
        with patch(
            "retrieval.adapters.content_search.ContentSearchAdapter"
        ) as mock_adapter_class:
            mock_config = MagicMock()
            mock_config.root = Path("/test")

            # Create mock response
            mock_response = MagicMock()
            mock_response.query = "function"
            mock_response.results = [
                MagicMock(
                    path="/test/code.py",
                    score=0.85,
                    snippet="def function():",
                    line_number=10,
                    match_type=MagicMock(value="content"),
                )
            ]
            mock_response.total = 1
            mock_response.page = 1
            mock_response.size = 10

            mock_adapter = MagicMock()
            mock_adapter.search = AsyncMock(return_value=mock_response)
            mock_adapter_class.return_value = mock_adapter

            actions = SearchActions(config=mock_config)
            response = actions.search_content("function")

            assert response.query == "function"
            assert len(response.results) == 1
            assert response.results[0].snippet == "def function():"
            assert response.results[0].line_number == 10
            assert response.search_type == SearchType.CONTENT

    def test_search_hybrid(self):
        """Test hybrid search."""
        with patch(
            "retrieval.adapters.hybrid_search.HybridSearchAdapter"
        ) as mock_adapter_class:
            mock_config = MagicMock()
            mock_config.root = Path("/test")
            mock_config.index.auto_index_on_search = False

            # Create mock response
            mock_response = MagicMock()
            mock_response.query = "test"
            mock_response.results = []
            mock_response.total = 0
            mock_response.page = 1
            mock_response.size = 10

            mock_adapter = MagicMock()
            mock_adapter.search = AsyncMock(return_value=mock_response)
            mock_adapter_class.return_value = mock_adapter

            actions = SearchActions(config=mock_config)
            response = actions.search_hybrid("test", auto_index=False)

            assert response.search_type == SearchType.HYBRID

    def test_adapter_caching(self):
        """Test that adapters are cached."""
        with patch(
            "retrieval.adapters.spotlight.SpotlightAdapter"
        ) as mock_adapter_class:
            mock_config = MagicMock()
            mock_config.root = Path("/test")

            mock_adapter = MagicMock()
            mock_adapter.search = AsyncMock(
                return_value=MagicMock(
                    query="test",
                    results=[],
                    total=0,
                    page=1,
                    size=10,
                )
            )
            mock_adapter_class.return_value = mock_adapter

            actions = SearchActions(config=mock_config)

            # First search
            actions.search_files("test1")
            # Second search - should use cached adapter
            actions.search_files("test2")

            # Adapter should only be created once
            assert mock_adapter_class.call_count == 1

    def test_search_pagination(self):
        """Test search with pagination."""
        with patch(
            "retrieval.adapters.spotlight.SpotlightAdapter"
        ) as mock_adapter_class:
            mock_config = MagicMock()
            mock_config.root = Path("/test")

            mock_response = MagicMock()
            mock_response.query = "test"
            mock_response.results = []
            mock_response.total = 100
            mock_response.page = 3
            mock_response.size = 20

            mock_adapter = MagicMock()
            mock_adapter.search = AsyncMock(return_value=mock_response)
            mock_adapter_class.return_value = mock_adapter

            actions = SearchActions(config=mock_config)
            response = actions.search_files("test", page=3, size=20)

            assert response.page == 3
            assert response.size == 20
            assert response.total == 100
