"""Unit tests for daemon actions."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.actions.daemon import (
    ActionResult,
    DaemonActions,
    DaemonStatus,
)


class TestDaemonStatus:
    """Tests for DaemonStatus dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        status = DaemonStatus(running=True)

        assert status.running is True
        assert status.pid is None
        assert status.uptime == ""
        assert status.indexing is False
        assert status.watcher_active is False
        assert status.files_indexed == 0

    def test_all_values(self):
        """Test all values are preserved."""
        status = DaemonStatus(
            running=True,
            pid=12345,
            uptime="2h 30m",
            indexing=True,
            watcher_active=True,
            files_indexed=100,
        )

        assert status.running is True
        assert status.pid == 12345
        assert status.uptime == "2h 30m"
        assert status.indexing is True
        assert status.watcher_active is True
        assert status.files_indexed == 100


class TestActionResult:
    """Tests for ActionResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        result = ActionResult(success=True, message="Done")

        assert result.success is True
        assert result.message == "Done"
        assert result.data is None

    def test_with_data(self):
        """Test result with data."""
        result = ActionResult(
            success=True,
            message="Done",
            data={"key": "value"},
        )

        assert result.data == {"key": "value"}


class TestDaemonActions:
    """Tests for DaemonActions class."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        actions = DaemonActions()

        assert actions.grpc_host == "127.0.0.1"
        assert actions.grpc_port == 50051
        assert actions.state_dir == Path.home() / ".maven"
        assert actions.daemon_module == "daemon.main"

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        actions = DaemonActions(
            grpc_host="localhost",
            grpc_port=9000,
            state_dir=Path("/tmp/maven"),
            daemon_module="custom.daemon",
        )

        assert actions.grpc_host == "localhost"
        assert actions.grpc_port == 9000
        assert actions.state_dir == Path("/tmp/maven")
        assert actions.daemon_module == "custom.daemon"

    def test_start_already_running(self):
        """Test start fails when daemon is already running."""
        actions = DaemonActions()

        with (
            patch.object(actions, "is_running", return_value=True),
            patch.object(actions, "get_pid", return_value=12345),
        ):
            result = actions.start()

            assert result.success is False
            assert "already running" in result.message
            assert "12345" in result.message

    def test_start_detached_success(self):
        """Test starting daemon in detached mode."""
        actions = DaemonActions(state_dir=Path("/tmp/test_maven"))

        with (
            patch.object(actions, "is_running", return_value=False),
            patch.object(
                actions._process_controller, "start"
            ) as mock_start,
        ):
            from core.process_manager.process_controller import ProcessResult

            mock_start.return_value = ProcessResult(
                success=True,
                message="Started",
                pid=54321,
            )

            result = actions.start(detach=True)

            assert result.success is True
            assert "background" in result.message
            mock_start.assert_called_once()

    def test_stop_not_running(self):
        """Test stop fails when daemon is not running."""
        actions = DaemonActions()

        with patch.object(actions, "is_running", return_value=False):
            result = actions.stop()

            assert result.success is False
            assert "not running" in result.message

    def test_stop_graceful_success(self):
        """Test graceful stop via gRPC."""
        actions = DaemonActions()

        with (
            patch.object(actions, "is_running", return_value=True),
            patch.object(actions, "_get_grpc_stub") as mock_stub,
        ):
            mock_response = MagicMock()
            mock_response.shutdown = True
            mock_stub.return_value.Shutdown.return_value = mock_response

            result = actions.stop()

            assert result.success is True
            assert "gracefully" in result.message

    def test_status_not_running(self):
        """Test status when daemon is not running."""
        actions = DaemonActions()

        with (
            patch.object(actions, "is_running", return_value=False),
            patch.object(actions, "get_pid", return_value=None),
        ):
            status = actions.status()

            assert status.running is False
            assert status.pid is None

    def test_status_running_with_grpc(self):
        """Test status when daemon is running with gRPC available."""
        actions = DaemonActions()

        with (
            patch.object(actions, "is_running", return_value=True),
            patch.object(actions, "get_pid", return_value=12345),
            patch.object(actions, "_get_grpc_stub") as mock_stub,
        ):
            mock_response = MagicMock()
            mock_response.running = True
            mock_response.pid = 12345
            mock_response.uptime = "1h 30m"
            mock_response.indexing = True
            mock_response.watcher_active = True
            mock_response.files_indexed = 50
            mock_stub.return_value.GetStatus.return_value = mock_response

            status = actions.status()

            assert status.running is True
            assert status.pid == 12345
            assert status.uptime == "1h 30m"
            assert status.indexing is True

    def test_ping_success(self):
        """Test successful ping."""
        actions = DaemonActions()

        with patch.object(actions, "_get_grpc_stub") as mock_stub:
            mock_response = MagicMock()
            mock_response.alive = True
            mock_response.version = "1.0.0"
            mock_stub.return_value.Ping.return_value = mock_response

            result = actions.ping()

            assert result.success is True
            assert "alive" in result.message
            assert result.data == {"version": "1.0.0"}

    def test_get_log_path(self):
        """Test getting log file path."""
        actions = DaemonActions(state_dir=Path("/tmp/maven"))

        log_path = actions.get_log_path()

        assert log_path == Path("/tmp/maven/logs/maven.daemon.log")
