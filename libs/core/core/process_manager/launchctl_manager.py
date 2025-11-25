"""macOS launchctl manager for process management."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from core.process_manager.plist_generator import LaunchAgentConfig, PlistGenerator


@dataclass
class LaunchctlResult:
    """Result from a launchctl operation.

    Attributes:
        success: Whether the operation succeeded
        message: Human-readable message about the result
        exit_code: Exit code from launchctl command
        stderr: Any error output
    """

    success: bool
    message: str
    exit_code: int = 0
    stderr: str = ""


class LaunchctlManager:
    """Manages macOS processes using launchctl and plist files.

    This class provides a high-level interface for managing launch agents
    on macOS, including loading, unloading, starting, stopping, and
    checking status of services.
    """

    MAVEN_LABEL = "com.maven.daemon"

    def __init__(self, label: str = MAVEN_LABEL):
        """Initialize the launchctl manager.

        Args:
            label: Unique identifier for the launch agent
        """
        self.label = label
        self._plist_path: Path | None = None

    @property
    def plist_path(self) -> Path:
        """Get the plist file path for this agent.

        Returns:
            Path to the plist file
        """
        if self._plist_path is None:
            self._plist_path = PlistGenerator.get_plist_path(self.label)
        return self._plist_path

    @plist_path.setter
    def plist_path(self, path: Path) -> None:
        """Set a custom plist path.

        Args:
            path: Custom path for the plist file
        """
        self._plist_path = path

    def is_macos(self) -> bool:
        """Check if running on macOS.

        Returns:
            True if running on macOS
        """
        return sys.platform == "darwin"

    def create_plist(
        self,
        program_path: str,
        program_arguments: list[str] | None = None,
        working_directory: str | None = None,
        stdout_path: str | None = None,
        stderr_path: str | None = None,
        environment_variables: dict[str, str] | None = None,
        run_at_load: bool = True,
        keep_alive: bool = True,
    ) -> LaunchctlResult:
        """Create a plist file for the launch agent.

        Args:
            program_path: Path to the executable
            program_arguments: Additional arguments for the program
            working_directory: Working directory for the process
            stdout_path: Path for stdout log file
            stderr_path: Path for stderr log file
            environment_variables: Environment variables for the process
            run_at_load: Whether to start immediately when loaded
            keep_alive: Whether to restart if the process exits

        Returns:
            LaunchctlResult indicating success or failure
        """
        config = LaunchAgentConfig(
            label=self.label,
            program_path=program_path,
            program_arguments=program_arguments or [],
            working_directory=working_directory,
            run_at_load=run_at_load,
            keep_alive=keep_alive,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            environment_variables=environment_variables or {},
        )

        try:
            PlistGenerator.write_plist(config, self.plist_path)
            return LaunchctlResult(
                success=True,
                message=f"Plist created at {self.plist_path}",
            )
        except OSError as e:
            return LaunchctlResult(
                success=False,
                message=f"Failed to create plist: {e}",
                stderr=str(e),
            )

    def load(self) -> LaunchctlResult:
        """Load the launch agent.

        Returns:
            LaunchctlResult indicating success or failure
        """
        if not self.is_macos():
            return LaunchctlResult(
                success=False,
                message="launchctl is only available on macOS",
                exit_code=1,
            )

        if not self.plist_path.exists():
            return LaunchctlResult(
                success=False,
                message=f"Plist file not found: {self.plist_path}",
                exit_code=1,
            )

        return self._run_launchctl("load", str(self.plist_path))

    def unload(self) -> LaunchctlResult:
        """Unload the launch agent.

        Returns:
            LaunchctlResult indicating success or failure
        """
        if not self.is_macos():
            return LaunchctlResult(
                success=False,
                message="launchctl is only available on macOS",
                exit_code=1,
            )

        if not self.plist_path.exists():
            return LaunchctlResult(
                success=False,
                message=f"Plist file not found: {self.plist_path}",
                exit_code=1,
            )

        return self._run_launchctl("unload", str(self.plist_path))

    def start(self) -> LaunchctlResult:
        """Start the launch agent.

        Returns:
            LaunchctlResult indicating success or failure
        """
        if not self.is_macos():
            return LaunchctlResult(
                success=False,
                message="launchctl is only available on macOS",
                exit_code=1,
            )

        return self._run_launchctl("start", self.label)

    def stop(self) -> LaunchctlResult:
        """Stop the launch agent.

        Returns:
            LaunchctlResult indicating success or failure
        """
        if not self.is_macos():
            return LaunchctlResult(
                success=False,
                message="launchctl is only available on macOS",
                exit_code=1,
            )

        return self._run_launchctl("stop", self.label)

    def kickstart(self) -> LaunchctlResult:
        """Kickstart the launch agent (force start even if already running).

        This is the modern macOS way to start services, equivalent to
        stopping and starting.

        Returns:
            LaunchctlResult indicating success or failure
        """
        if not self.is_macos():
            return LaunchctlResult(
                success=False,
                message="launchctl is only available on macOS",
                exit_code=1,
            )

        uid = self._get_uid()
        service_target = f"gui/{uid}/{self.label}"

        return self._run_launchctl("kickstart", "-k", service_target)

    def bootstrap(self) -> LaunchctlResult:
        """Bootstrap (load) the launch agent using modern launchctl API.

        This is the modern equivalent of 'launchctl load'.

        Returns:
            LaunchctlResult indicating success or failure
        """
        if not self.is_macos():
            return LaunchctlResult(
                success=False,
                message="launchctl is only available on macOS",
                exit_code=1,
            )

        if not self.plist_path.exists():
            return LaunchctlResult(
                success=False,
                message=f"Plist file not found: {self.plist_path}",
                exit_code=1,
            )

        uid = self._get_uid()
        domain_target = f"gui/{uid}"

        return self._run_launchctl("bootstrap", domain_target, str(self.plist_path))

    def bootout(self) -> LaunchctlResult:
        """Bootout (unload) the launch agent using modern launchctl API.

        This is the modern equivalent of 'launchctl unload'.

        Returns:
            LaunchctlResult indicating success or failure
        """
        if not self.is_macos():
            return LaunchctlResult(
                success=False,
                message="launchctl is only available on macOS",
                exit_code=1,
            )

        uid = self._get_uid()
        service_target = f"gui/{uid}/{self.label}"

        return self._run_launchctl("bootout", service_target)

    def is_loaded(self) -> bool:
        """Check if the launch agent is loaded.

        Returns:
            True if the agent is loaded
        """
        if not self.is_macos():
            return False

        result = self._run_launchctl("list")
        if not result.success:
            return False

        # Check if our label appears in the list
        return self.label in result.message

    def get_pid(self) -> int | None:
        """Get the PID of the running process.

        Returns:
            PID if running, None otherwise
        """
        if not self.is_macos():
            return None

        result = self._run_launchctl("list", self.label)
        if not result.success:
            return None

        # Parse the output to find PID
        # launchctl list <label> outputs: "PID Status Label" or details
        lines = result.message.strip().split("\n")
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 1 and parts[0].isdigit():
                return int(parts[0])

        return None

    def print_status(self) -> LaunchctlResult:
        """Print detailed status of the launch agent.

        Returns:
            LaunchctlResult with status information
        """
        if not self.is_macos():
            return LaunchctlResult(
                success=False,
                message="launchctl is only available on macOS",
                exit_code=1,
            )

        uid = self._get_uid()
        service_target = f"gui/{uid}/{self.label}"

        return self._run_launchctl("print", service_target)

    def remove_plist(self) -> LaunchctlResult:
        """Remove the plist file.

        Returns:
            LaunchctlResult indicating success or failure
        """
        try:
            if self.plist_path.exists():
                self.plist_path.unlink()
                return LaunchctlResult(
                    success=True,
                    message=f"Plist removed: {self.plist_path}",
                )
            return LaunchctlResult(
                success=True,
                message="Plist file does not exist",
            )
        except OSError as e:
            return LaunchctlResult(
                success=False,
                message=f"Failed to remove plist: {e}",
                stderr=str(e),
            )

    def _run_launchctl(self, *args: str) -> LaunchctlResult:
        """Run a launchctl command.

        Args:
            *args: Arguments to pass to launchctl

        Returns:
            LaunchctlResult with command output
        """
        try:
            result = subprocess.run(
                ["launchctl", *args],
                capture_output=True,
                text=True,
                check=False,
            )

            success = result.returncode == 0
            message = result.stdout if success else result.stderr or result.stdout

            return LaunchctlResult(
                success=success,
                message=message.strip(),
                exit_code=result.returncode,
                stderr=result.stderr.strip(),
            )
        except FileNotFoundError:
            return LaunchctlResult(
                success=False,
                message="launchctl command not found",
                exit_code=127,
            )
        except subprocess.SubprocessError as e:
            return LaunchctlResult(
                success=False,
                message=f"Command failed: {e}",
                exit_code=1,
                stderr=str(e),
            )

    @staticmethod
    def _get_uid() -> int:
        """Get the current user ID.

        Returns:
            Current user's UID
        """
        import os

        return os.getuid()
