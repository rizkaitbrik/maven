"""Unit tests for the launchctl manager."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.process_manager.launchctl_manager import (
    LaunchctlManager,
    LaunchctlResult,
)


class TestLaunchctlResult:
    """Tests for LaunchctlResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        result = LaunchctlResult(success=True, message="Success")

        assert result.success is True
        assert result.message == "Success"
        assert result.exit_code == 0
        assert result.stderr == ""

    def test_failure_result(self):
        """Test failure result with all fields."""
        result = LaunchctlResult(
            success=False,
            message="Operation failed",
            exit_code=1,
            stderr="Error details",
        )

        assert result.success is False
        assert result.message == "Operation failed"
        assert result.exit_code == 1
        assert result.stderr == "Error details"


class TestLaunchctlManager:
    """Tests for LaunchctlManager class."""

    def test_init_default_label(self):
        """Test initialization with default label."""
        manager = LaunchctlManager()

        assert manager.label == "com.maven.daemon"

    def test_init_custom_label(self):
        """Test initialization with custom label."""
        manager = LaunchctlManager(label="com.test.service")

        assert manager.label == "com.test.service"

    def test_plist_path_default(self):
        """Test default plist path."""
        manager = LaunchctlManager(label="com.test.service")

        expected = Path.home() / "Library" / "LaunchAgents" / "com.test.service.plist"
        assert manager.plist_path == expected

    def test_plist_path_custom(self):
        """Test setting custom plist path."""
        manager = LaunchctlManager()
        custom_path = Path("/tmp/custom.plist")

        manager.plist_path = custom_path

        assert manager.plist_path == custom_path

    def test_is_macos_true(self):
        """Test is_macos returns True on macOS."""
        manager = LaunchctlManager()

        with patch.object(sys, "platform", "darwin"):
            assert manager.is_macos() is True

    def test_is_macos_false(self):
        """Test is_macos returns False on other platforms."""
        manager = LaunchctlManager()

        with patch.object(sys, "platform", "linux"):
            assert manager.is_macos() is False

    def test_create_plist(self):
        """Test creating a plist file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LaunchctlManager()
            plist_path = Path(tmpdir) / "test.plist"
            manager.plist_path = plist_path

            result = manager.create_plist(
                program_path="/usr/bin/test",
                program_arguments=["--arg"],
                stdout_path="/tmp/stdout.log",
            )

            assert result.success is True
            assert plist_path.exists()

    def test_load_not_macos(self):
        """Test load fails on non-macOS."""
        manager = LaunchctlManager()

        with patch.object(sys, "platform", "linux"):
            result = manager.load()

            assert result.success is False
            assert "only available on macOS" in result.message

    def test_load_plist_not_found(self):
        """Test load fails when plist doesn't exist."""
        manager = LaunchctlManager()
        manager.plist_path = Path("/nonexistent.plist")

        with patch.object(sys, "platform", "darwin"):
            result = manager.load()

            assert result.success is False
            assert "not found" in result.message

    def test_unload_not_macos(self):
        """Test unload fails on non-macOS."""
        manager = LaunchctlManager()

        with patch.object(sys, "platform", "linux"):
            result = manager.unload()

            assert result.success is False
            assert "only available on macOS" in result.message

    def test_start_not_macos(self):
        """Test start fails on non-macOS."""
        manager = LaunchctlManager()

        with patch.object(sys, "platform", "linux"):
            result = manager.start()

            assert result.success is False
            assert "only available on macOS" in result.message

    def test_stop_not_macos(self):
        """Test stop fails on non-macOS."""
        manager = LaunchctlManager()

        with patch.object(sys, "platform", "linux"):
            result = manager.stop()

            assert result.success is False
            assert "only available on macOS" in result.message

    def test_is_loaded_not_macos(self):
        """Test is_loaded returns False on non-macOS."""
        manager = LaunchctlManager()

        with patch.object(sys, "platform", "linux"):
            assert manager.is_loaded() is False

    def test_get_pid_not_macos(self):
        """Test get_pid returns None on non-macOS."""
        manager = LaunchctlManager()

        with patch.object(sys, "platform", "linux"):
            assert manager.get_pid() is None

    def test_remove_plist_exists(self):
        """Test removing an existing plist file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = LaunchctlManager()
            plist_path = Path(tmpdir) / "test.plist"
            plist_path.write_text("test")
            manager.plist_path = plist_path

            result = manager.remove_plist()

            assert result.success is True
            assert not plist_path.exists()

    def test_remove_plist_not_exists(self):
        """Test removing a non-existent plist file."""
        manager = LaunchctlManager()
        manager.plist_path = Path("/nonexistent.plist")

        result = manager.remove_plist()

        assert result.success is True
        assert "does not exist" in result.message

    @patch("subprocess.run")
    def test_run_launchctl_success(self, mock_run):
        """Test successful launchctl command execution."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Command output",
            stderr="",
        )

        manager = LaunchctlManager()
        result = manager._run_launchctl("list")

        assert result.success is True
        assert result.message == "Command output"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_run_launchctl_failure(self, mock_run):
        """Test failed launchctl command execution."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error occurred",
        )

        manager = LaunchctlManager()
        result = manager._run_launchctl("invalid")

        assert result.success is False
        assert result.exit_code == 1

    @patch("subprocess.run")
    def test_run_launchctl_command_not_found(self, mock_run):
        """Test launchctl command not found."""
        mock_run.side_effect = FileNotFoundError()

        manager = LaunchctlManager()
        result = manager._run_launchctl("list")

        assert result.success is False
        assert "not found" in result.message
        assert result.exit_code == 127
