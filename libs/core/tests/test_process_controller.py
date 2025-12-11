"""Unit tests for the process controller."""

import signal
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.process_manager.process_controller import ProcessController, ProcessResult


class TestProcessResult:
    """Tests for ProcessResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        result = ProcessResult(success=True, message="Success")

        assert result.success is True
        assert result.message == "Success"
        assert result.pid is None

    def test_with_pid(self):
        """Test result with PID."""
        result = ProcessResult(success=True, message="Started", pid=12345)

        assert result.pid == 12345


class TestProcessController:
    """Tests for ProcessController class."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        controller = ProcessController()

        assert controller.label == "com.maven.daemon"
        assert controller.program_path is None
        assert controller.pid_file == Path.home() / ".maven" / "daemon.pid"

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        controller = ProcessController(
            label="com.test.service",
            program_path="/usr/bin/test",
            pid_file=Path("/tmp/test.pid"),
        )

        assert controller.label == "com.test.service"
        assert controller.program_path == "/usr/bin/test"
        assert controller.pid_file == Path("/tmp/test.pid")

    def test_is_macos_true(self):
        """Test is_macos returns True on macOS."""
        controller = ProcessController()

        with patch.object(sys, "platform", "darwin"):
            assert controller.is_macos() is True

    def test_is_macos_false(self):
        """Test is_macos returns False on other platforms."""
        controller = ProcessController()

        with patch.object(sys, "platform", "linux"):
            assert controller.is_macos() is False

    def test_start_no_program_path(self):
        """Test start fails without program path."""
        controller = ProcessController()

        result = controller.start()

        assert result.success is False
        assert "not specified" in result.message

    def test_start_with_subprocess_fallback(self):
        """Test start uses subprocess on non-macOS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "test.pid"
            controller = ProcessController(
                program_path="/bin/sleep",
                pid_file=pid_file,
            )

            with (
                patch.object(sys, "platform", "linux"),
                patch("subprocess.Popen") as mock_popen,
            ):
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_popen.return_value = mock_process

                result = controller.start(use_launchctl=False)

                assert result.success is True
                assert result.pid == 12345
                assert pid_file.exists()
                assert pid_file.read_text() == "12345"

    def test_stop_with_signal(self):
        """Test stop uses SIGTERM on non-macOS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "test.pid"
            pid_file.write_text("12345")

            controller = ProcessController(
                pid_file=pid_file,
            )

            with (
                patch.object(sys, "platform", "linux"),
                patch("os.kill") as mock_kill,
            ):
                result = controller.stop(use_launchctl=False)

                assert result.success is True
                mock_kill.assert_called_once_with(12345, signal.SIGTERM)
                assert not pid_file.exists()

    def test_stop_no_pid_file(self):
        """Test stop fails when no PID file exists."""
        controller = ProcessController(
            pid_file=Path("/nonexistent.pid"),
        )

        with patch.object(sys, "platform", "linux"):
            result = controller.stop(use_launchctl=False)

            assert result.success is False
            assert "not running" in result.message

    def test_stop_process_not_found(self):
        """Test stop succeeds when process is already dead."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "test.pid"
            pid_file.write_text("12345")

            controller = ProcessController(
                pid_file=pid_file,
            )

            with (
                patch.object(sys, "platform", "linux"),
                patch("os.kill", side_effect=ProcessLookupError),
            ):
                result = controller.stop(use_launchctl=False)

                assert result.success is True
                assert "not running" in result.message
                assert not pid_file.exists()

    def test_is_running_with_pid_file(self):
        """Test is_running checks PID file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "test.pid"
            pid_file.write_text("12345")

            controller = ProcessController(
                pid_file=pid_file,
            )

            with (
                patch.object(sys, "platform", "linux"),
                patch("os.kill"),  # Process exists
            ):
                assert controller.is_running(use_launchctl=False) is True

    def test_is_running_process_dead(self):
        """Test is_running returns False when process is dead."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "test.pid"
            pid_file.write_text("12345")

            controller = ProcessController(
                pid_file=pid_file,
            )

            with (
                patch.object(sys, "platform", "linux"),
                patch("os.kill", side_effect=OSError),
            ):
                assert controller.is_running(use_launchctl=False) is False

    def test_get_pid_from_file(self):
        """Test get_pid reads from PID file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "test.pid"
            pid_file.write_text("54321")

            controller = ProcessController(
                pid_file=pid_file,
            )

            with patch.object(sys, "platform", "linux"):
                pid = controller.get_pid(use_launchctl=False)

                assert pid == 54321

    def test_get_pid_no_file(self):
        """Test get_pid returns None when no PID file."""
        controller = ProcessController(
            pid_file=Path("/nonexistent.pid"),
        )

        with patch.object(sys, "platform", "linux"):
            pid = controller.get_pid(use_launchctl=False)

            assert pid is None

    def test_get_pid_invalid_content(self):
        """Test get_pid returns None with invalid PID file content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "test.pid"
            pid_file.write_text("not a number")

            controller = ProcessController(
                pid_file=pid_file,
            )

            with patch.object(sys, "platform", "linux"):
                pid = controller.get_pid(use_launchctl=False)

                assert pid is None

    def test_restart(self):
        """Test restart stops and starts the process."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "test.pid"

            controller = ProcessController(
                program_path="/bin/sleep",
                pid_file=pid_file,
            )

            with (
                patch.object(sys, "platform", "linux"),
                patch.object(controller, "stop") as mock_stop,
                patch.object(controller, "start") as mock_start,
            ):
                mock_stop.return_value = ProcessResult(
                    success=True,
                    message="Stopped",
                )

                mock_start.return_value = ProcessResult(
                    success=True,
                    message="Started",
                    pid=12345,
                )

                result = controller.restart(use_launchctl=False)

                assert result.success is True
                mock_stop.assert_called_once()
                mock_start.assert_called_once()

    def test_uninstall_not_macos(self):
        """Test uninstall on non-macOS is a no-op."""
        controller = ProcessController()

        with patch.object(sys, "platform", "linux"):
            result = controller.uninstall()

            assert result.success is True
            assert "Not on macOS" in result.message
