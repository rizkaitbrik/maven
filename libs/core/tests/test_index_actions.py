"""Unit tests for index actions."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.actions.index import (
    ActionResult,
    IndexActions,
    IndexStats,
)


class TestIndexStats:
    """Tests for IndexStats dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        stats = IndexStats(
            file_count=100,
            total_size_bytes=1024000,
            last_indexed_at=1234567890.0,
            db_path="/tmp/index.db",
        )

        assert stats.file_count == 100
        assert stats.total_size_bytes == 1024000
        assert stats.last_indexed_at == 1234567890.0
        assert stats.db_path == "/tmp/index.db"
        assert stats.watcher_enabled is False

    def test_with_watcher(self):
        """Test stats with watcher enabled."""
        stats = IndexStats(
            file_count=50,
            total_size_bytes=512000,
            last_indexed_at=None,
            db_path="/tmp/test.db",
            watcher_enabled=True,
        )

        assert stats.watcher_enabled is True


class TestActionResult:
    """Tests for ActionResult dataclass."""

    def test_success_result(self):
        """Test successful action result."""
        result = ActionResult(
            success=True,
            message="Operation completed",
        )

        assert result.success is True
        assert result.message == "Operation completed"
        assert result.data is None

    def test_failure_result_with_data(self):
        """Test failure result with data."""
        result = ActionResult(
            success=False,
            message="Operation failed",
            data={"error_code": 500},
        )

        assert result.success is False
        assert result.data == {"error_code": 500}


class TestIndexActions:
    """Tests for IndexActions class."""

    def test_config_lazy_loading(self):
        """Test that config is lazily loaded."""
        with patch(
            "retrieval.services.config_manager.ConfigManager"
        ) as mock_config_manager:
            mock_config = MagicMock()
            mock_config_manager.return_value.config = mock_config

            actions = IndexActions()

            # Config should not be loaded yet
            assert actions._config is None

            # Access config to trigger loading
            config = actions.config

            assert config is mock_config
            mock_config_manager.assert_called_once()

    def test_config_custom(self):
        """Test using custom config."""
        mock_config = MagicMock()
        actions = IndexActions(config=mock_config)

        assert actions.config is mock_config

    def test_index_manager_lazy_loading(self):
        """Test that index manager is lazily loaded."""
        with patch(
            "retrieval.services.index_manager.IndexManager"
        ) as mock_index_manager:
            mock_config = MagicMock()
            actions = IndexActions(config=mock_config)

            # Index manager should not be created yet
            assert actions._index_manager is None

            # Access to trigger creation
            _ = actions.index_manager

            mock_index_manager.assert_called_once()

    def test_indexer_lazy_loading(self):
        """Test that indexer is lazily loaded."""
        with (
            patch("retrieval.services.index_manager.IndexManager"),
            patch(
                "retrieval.services.background_indexer.BackgroundIndexer"
            ) as mock_bg_indexer,
        ):
            mock_config = MagicMock()
            actions = IndexActions(config=mock_config)

            # Indexer should not be created yet
            assert actions._indexer is None

            # Access to trigger creation
            _ = actions.indexer

            mock_bg_indexer.assert_called_once()

    def test_get_stats(self):
        """Test getting index statistics."""
        mock_config = MagicMock()
        mock_config.index.enable_watcher = True

        mock_index_manager = MagicMock()
        mock_index_manager.get_stats.return_value = {
            "file_count": 100,
            "total_size_bytes": 1024000,
            "last_indexed_at": 1234567890.0,
            "db_path": "/tmp/index.db",
        }

        actions = IndexActions(config=mock_config)
        actions._index_manager = mock_index_manager

        stats = actions.get_stats

        assert stats.file_count == 100
        assert stats.total_size_bytes == 1024000
        assert stats.last_indexed_at == 1234567890.0
        assert stats.db_path == "/tmp/index.db"
        assert stats.watcher_enabled is True

    def test_start_indexing(self):
        """Test starting indexing."""
        mock_config = MagicMock()
        mock_config.root = Path("/home/user/project")

        mock_indexer = MagicMock()

        actions = IndexActions(config=mock_config)
        actions._indexer = mock_indexer

        result = actions.start_indexing()

        assert result.success is True
        assert "started" in result.message.lower()
        mock_indexer.start_indexing.assert_called_once()

    def test_start_indexing_custom_root(self):
        """Test starting indexing with custom root."""
        mock_config = MagicMock()
        mock_config.root = Path("/home/user/default")

        mock_indexer = MagicMock()

        actions = IndexActions(config=mock_config)
        actions._indexer = mock_indexer

        custom_root = Path("/home/user/custom")
        result = actions.start_indexing(root=custom_root)

        assert result.success is True
        assert str(custom_root) in result.message
        mock_indexer.start_indexing.assert_called_once_with(
            root=custom_root,
            rebuild=False,
            progress_callback=None,
        )

    def test_stop_indexing_not_running(self):
        """Test stopping indexing when not running."""
        mock_indexer = MagicMock()
        mock_indexer.is_indexing.return_value = False

        mock_config = MagicMock()
        actions = IndexActions(config=mock_config)
        actions._indexer = mock_indexer

        result = actions.stop_indexing()

        assert result.success is False
        assert "not in progress" in result.message

    def test_stop_indexing_running(self):
        """Test stopping indexing when running."""
        mock_indexer = MagicMock()
        mock_indexer.is_indexing.return_value = True

        mock_config = MagicMock()
        actions = IndexActions(config=mock_config)
        actions._indexer = mock_indexer

        result = actions.stop_indexing()

        assert result.success is True
        mock_indexer.stop_indexing.assert_called_once()

    def test_is_indexing(self):
        """Test checking if indexing is in progress."""
        mock_indexer = MagicMock()
        mock_indexer.is_indexing.return_value = True

        mock_config = MagicMock()
        actions = IndexActions(config=mock_config)
        actions._indexer = mock_indexer

        assert actions.is_indexing() is True

    def test_get_progress(self):
        """Test getting indexing progress."""
        mock_indexer = MagicMock()
        mock_indexer.get_progress.return_value = (50, 100)

        mock_config = MagicMock()
        actions = IndexActions(config=mock_config)
        actions._indexer = mock_indexer

        current, total = actions.get_progress()

        assert current == 50
        assert total == 100

    def test_clear_index(self):
        """Test clearing the index."""
        mock_index_manager = MagicMock()
        mock_config = MagicMock()

        actions = IndexActions(config=mock_config)
        actions._index_manager = mock_index_manager

        result = actions.clear_index()

        assert result.success is True
        mock_index_manager.clear.assert_called_once()

    def test_get_watcher_status(self):
        """Test getting file watcher status."""
        mock_indexer = MagicMock()
        mock_indexer.get_watcher_status.return_value = True

        mock_config = MagicMock()
        actions = IndexActions(config=mock_config)
        actions._indexer = mock_indexer

        assert actions.get_watcher_status() is True
