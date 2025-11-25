"""Unit tests for the plist generator."""

import plistlib
import tempfile
from pathlib import Path

import pytest

from core.process_manager.plist_generator import (
    LaunchAgentConfig,
    PlistGenerator,
)


class TestLaunchAgentConfig:
    """Tests for LaunchAgentConfig dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = LaunchAgentConfig(
            label="com.test.service",
            program_path="/usr/bin/test",
        )

        assert config.label == "com.test.service"
        assert config.program_path == "/usr/bin/test"
        assert config.program_arguments == []
        assert config.working_directory is None
        assert config.run_at_load is True
        assert config.keep_alive is True
        assert config.stdout_path is None
        assert config.stderr_path is None
        assert config.environment_variables == {}

    def test_custom_values(self):
        """Test that custom values are preserved."""
        config = LaunchAgentConfig(
            label="com.test.service",
            program_path="/usr/bin/test",
            program_arguments=["--arg1", "--arg2"],
            working_directory="/home/user",
            run_at_load=False,
            keep_alive=False,
            stdout_path="/tmp/stdout.log",
            stderr_path="/tmp/stderr.log",
            environment_variables={"KEY": "VALUE"},
        )

        assert config.program_arguments == ["--arg1", "--arg2"]
        assert config.working_directory == "/home/user"
        assert config.run_at_load is False
        assert config.keep_alive is False
        assert config.stdout_path == "/tmp/stdout.log"
        assert config.stderr_path == "/tmp/stderr.log"
        assert config.environment_variables == {"KEY": "VALUE"}


class TestPlistGenerator:
    """Tests for PlistGenerator class."""

    def test_generate_plist_minimal(self):
        """Test generating plist with minimal configuration."""
        config = LaunchAgentConfig(
            label="com.test.daemon",
            program_path="/usr/bin/daemon",
        )

        plist = PlistGenerator.generate_plist(config)

        assert plist["Label"] == "com.test.daemon"
        assert plist["ProgramArguments"] == ["/usr/bin/daemon"]
        assert plist["RunAtLoad"] is True
        assert plist["KeepAlive"] is True
        assert "WorkingDirectory" not in plist
        assert "StandardOutPath" not in plist
        assert "StandardErrorPath" not in plist
        assert "EnvironmentVariables" not in plist

    def test_generate_plist_full(self):
        """Test generating plist with full configuration."""
        config = LaunchAgentConfig(
            label="com.maven.daemon",
            program_path="/usr/local/bin/maven-daemon",
            program_arguments=["--config", "/etc/maven.yaml"],
            working_directory="/var/maven",
            run_at_load=True,
            keep_alive=True,
            stdout_path="/var/log/maven/stdout.log",
            stderr_path="/var/log/maven/stderr.log",
            environment_variables={"MAVEN_HOME": "/opt/maven"},
        )

        plist = PlistGenerator.generate_plist(config)

        assert plist["Label"] == "com.maven.daemon"
        assert plist["ProgramArguments"] == [
            "/usr/local/bin/maven-daemon",
            "--config",
            "/etc/maven.yaml",
        ]
        assert plist["RunAtLoad"] is True
        assert plist["KeepAlive"] is True
        assert plist["WorkingDirectory"] == "/var/maven"
        assert plist["StandardOutPath"] == "/var/log/maven/stdout.log"
        assert plist["StandardErrorPath"] == "/var/log/maven/stderr.log"
        assert plist["EnvironmentVariables"] == {"MAVEN_HOME": "/opt/maven"}

    def test_write_and_read_plist(self):
        """Test writing and reading a plist file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.plist"

            config = LaunchAgentConfig(
                label="com.test.service",
                program_path="/usr/bin/test",
                program_arguments=["--verbose"],
            )

            # Write plist
            PlistGenerator.write_plist(config, output_path)

            assert output_path.exists()

            # Read plist
            read_plist = PlistGenerator.read_plist(output_path)

            assert read_plist["Label"] == "com.test.service"
            assert read_plist["ProgramArguments"] == ["/usr/bin/test", "--verbose"]

    def test_write_plist_creates_parent_dirs(self):
        """Test that write_plist creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "test.plist"

            config = LaunchAgentConfig(
                label="com.test.service",
                program_path="/usr/bin/test",
            )

            PlistGenerator.write_plist(config, output_path)

            assert output_path.exists()

    def test_read_plist_file_not_found(self):
        """Test that reading non-existent plist raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            PlistGenerator.read_plist(Path("/nonexistent/path.plist"))

    def test_read_invalid_plist(self):
        """Test that reading invalid plist raises exception."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".plist", delete=False) as f:
            f.write("not a valid plist")
            f.flush()

            with pytest.raises(plistlib.InvalidFileException):
                PlistGenerator.read_plist(Path(f.name))

    def test_get_launch_agents_dir(self):
        """Test getting the LaunchAgents directory."""
        agents_dir = PlistGenerator.get_launch_agents_dir()

        assert agents_dir == Path.home() / "Library" / "LaunchAgents"

    def test_get_plist_path(self):
        """Test getting plist path for a label."""
        path = PlistGenerator.get_plist_path("com.maven.daemon")

        expected = Path.home() / "Library" / "LaunchAgents" / "com.maven.daemon.plist"
        assert path == expected
