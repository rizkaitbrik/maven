"""Plist generator for macOS launch agent configuration."""

import plistlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LaunchAgentConfig:
    """Configuration for a macOS launch agent.

    Attributes:
        label: Unique identifier for the launch agent (e.g., 'com.maven.daemon')
        program_path: Path to the executable or script
        program_arguments: Additional arguments for the program
        working_directory: Working directory for the process
        run_at_load: Whether to start immediately when loaded
        keep_alive: Whether to restart if the process exits
        stdout_path: Path for stdout log file
        stderr_path: Path for stderr log file
        environment_variables: Environment variables for the process
    """

    label: str
    program_path: str
    program_arguments: list[str] = field(default_factory=list)
    working_directory: str | None = None
    run_at_load: bool = True
    keep_alive: bool = True
    stdout_path: str | None = None
    stderr_path: str | None = None
    environment_variables: dict[str, str] = field(default_factory=dict)


class PlistGenerator:
    """Generates macOS plist files for launch agent configuration."""

    @staticmethod
    def generate_plist(config: LaunchAgentConfig) -> dict[str, Any]:
        """Generate a plist dictionary from configuration.

        Args:
            config: Launch agent configuration

        Returns:
            Dictionary suitable for plistlib serialization
        """
        plist_dict: dict[str, Any] = {
            "Label": config.label,
            "ProgramArguments": [config.program_path, *config.program_arguments],
            "RunAtLoad": config.run_at_load,
            "KeepAlive": config.keep_alive,
        }

        if config.working_directory:
            plist_dict["WorkingDirectory"] = config.working_directory

        if config.stdout_path:
            plist_dict["StandardOutPath"] = config.stdout_path

        if config.stderr_path:
            plist_dict["StandardErrorPath"] = config.stderr_path

        if config.environment_variables:
            plist_dict["EnvironmentVariables"] = config.environment_variables

        return plist_dict

    @staticmethod
    def write_plist(config: LaunchAgentConfig, output_path: Path) -> None:
        """Write a plist file from configuration.

        Args:
            config: Launch agent configuration
            output_path: Path where the plist file will be written
        """
        plist_dict = PlistGenerator.generate_plist(config)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            plistlib.dump(plist_dict, f)

    @staticmethod
    def read_plist(path: Path) -> dict[str, Any]:
        """Read a plist file.

        Args:
            path: Path to the plist file

        Returns:
            Dictionary with plist contents

        Raises:
            FileNotFoundError: If the plist file doesn't exist
            plistlib.InvalidFileException: If the file is not valid plist
        """
        with open(path, "rb") as f:
            return plistlib.load(f)

    @staticmethod
    def get_launch_agents_dir() -> Path:
        """Get the user's LaunchAgents directory.

        Returns:
            Path to ~/Library/LaunchAgents
        """
        return Path.home() / "Library" / "LaunchAgents"

    @staticmethod
    def get_plist_path(label: str) -> Path:
        """Get the standard plist path for a given label.

        Args:
            label: Launch agent label (e.g., 'com.maven.daemon')

        Returns:
            Path to the plist file
        """
        return PlistGenerator.get_launch_agents_dir() / f"{label}.plist"
