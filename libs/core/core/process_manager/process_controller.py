"""Platform-agnostic process controller with macOS launchctl support."""

import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from core.process_manager.launchctl_manager import LaunchctlManager, LaunchctlResult


@dataclass
class ProcessResult:
    """Result from a process operation.

    Attributes:
        success: Whether the operation succeeded
        message: Human-readable message about the result
        pid: Process ID if applicable
    """

    success: bool
    message: str
    pid: int | None = None


class ProcessController:
    """Platform-agnostic process controller with macOS launchctl support.

    This class provides a unified interface for process management that
    automatically uses launchctl on macOS and falls back to standard
    subprocess management on other platforms.
    """

    def __init__(
        self,
        label: str = "com.maven.daemon",
        program_path: str | None = None,
        pid_file: Path | None = None,
    ):
        """Initialize the process controller.

        Args:
            label: Unique identifier for the service
            program_path: Path to the program executable
            pid_file: Path to PID file for non-launchctl fallback
        """
        self.label = label
        self.program_path = program_path
        self.pid_file = pid_file or Path.home() / ".maven" / "daemon.pid"

        # Initialize launchctl manager for macOS
        self._launchctl = LaunchctlManager(label)

    def is_macos(self) -> bool:
        """Check if running on macOS.

        Returns:
            True if running on macOS
        """
        return sys.platform == "darwin"

    def start(
        self,
        program_arguments: list[str] | None = None,
        working_directory: str | None = None,
        stdout_path: str | None = None,
        stderr_path: str | None = None,
        environment_variables: dict[str, str] | None = None,
        use_launchctl: bool = True,
    ) -> ProcessResult:
        """Start the process.

        On macOS with use_launchctl=True, this will:
        1. Create a plist file
        2. Load the launch agent
        3. Start the service

        On other platforms or with use_launchctl=False, this will:
        1. Start the process using subprocess
        2. Write the PID to a file

        Args:
            program_arguments: Additional arguments for the program
            working_directory: Working directory for the process
            stdout_path: Path for stdout log file
            stderr_path: Path for stderr log file
            environment_variables: Environment variables for the process
            use_launchctl: Whether to use launchctl on macOS

        Returns:
            ProcessResult indicating success or failure
        """
        if not self.program_path:
            return ProcessResult(
                success=False,
                message="Program path not specified",
            )

        if self.is_macos() and use_launchctl:
            return self._start_with_launchctl(
                program_arguments=program_arguments,
                working_directory=working_directory,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                environment_variables=environment_variables,
            )
        else:
            return self._start_with_subprocess(
                program_arguments=program_arguments,
                working_directory=working_directory,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                environment_variables=environment_variables,
            )

    def stop(self, use_launchctl: bool = True) -> ProcessResult:
        """Stop the process.

        Args:
            use_launchctl: Whether to use launchctl on macOS

        Returns:
            ProcessResult indicating success or failure
        """
        if self.is_macos() and use_launchctl:
            return self._stop_with_launchctl()
        else:
            return self._stop_with_signal()

    def is_running(self, use_launchctl: bool = True) -> bool:
        """Check if the process is running.

        Args:
            use_launchctl: Whether to use launchctl on macOS

        Returns:
            True if the process is running
        """
        if self.is_macos() and use_launchctl:
            return self._launchctl.is_loaded()

        return self._is_running_via_pid()

    def get_pid(self, use_launchctl: bool = True) -> int | None:
        """Get the process ID.

        Args:
            use_launchctl: Whether to use launchctl on macOS

        Returns:
            PID if running, None otherwise
        """
        if self.is_macos() and use_launchctl:
            return self._launchctl.get_pid()

        return self._get_pid_from_file()

    def restart(
        self,
        program_arguments: list[str] | None = None,
        working_directory: str | None = None,
        stdout_path: str | None = None,
        stderr_path: str | None = None,
        environment_variables: dict[str, str] | None = None,
        use_launchctl: bool = True,
    ) -> ProcessResult:
        """Restart the process.

        Args:
            program_arguments: Additional arguments for the program
            working_directory: Working directory for the process
            stdout_path: Path for stdout log file
            stderr_path: Path for stderr log file
            environment_variables: Environment variables for the process
            use_launchctl: Whether to use launchctl on macOS

        Returns:
            ProcessResult indicating success or failure
        """
        # Stop the process
        stop_result = self.stop(use_launchctl=use_launchctl)
        if not stop_result.success:
            # Continue even if stop fails (process might not be running)
            pass

        # Start the process
        return self.start(
            program_arguments=program_arguments,
            working_directory=working_directory,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            environment_variables=environment_variables,
            use_launchctl=use_launchctl,
        )

    def uninstall(self) -> ProcessResult:
        """Uninstall the launch agent (macOS only).

        This stops the process, unloads the agent, and removes the plist file.

        Returns:
            ProcessResult indicating success or failure
        """
        if not self.is_macos():
            return ProcessResult(
                success=True,
                message="Not on macOS, nothing to uninstall",
            )

        # Stop and unload
        self._launchctl.bootout()

        # Remove plist
        result = self._launchctl.remove_plist()

        return ProcessResult(
            success=result.success,
            message=result.message,
        )

    def _start_with_launchctl(
        self,
        program_arguments: list[str] | None = None,
        working_directory: str | None = None,
        stdout_path: str | None = None,
        stderr_path: str | None = None,
        environment_variables: dict[str, str] | None = None,
    ) -> ProcessResult:
        """Start process using launchctl on macOS.

        Args:
            program_arguments: Additional arguments for the program
            working_directory: Working directory for the process
            stdout_path: Path for stdout log file
            stderr_path: Path for stderr log file
            environment_variables: Environment variables for the process

        Returns:
            ProcessResult indicating success or failure
        """
        # Create plist
        create_result = self._launchctl.create_plist(
            program_path=self.program_path,  # type: ignore
            program_arguments=program_arguments,
            working_directory=working_directory,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            environment_variables=environment_variables,
            run_at_load=True,
            keep_alive=True,
        )

        if not create_result.success:
            return ProcessResult(
                success=False,
                message=f"Failed to create plist: {create_result.message}",
            )

        # Bootstrap (load) the agent - this also starts it due to RunAtLoad
        bootstrap_result = self._launchctl.bootstrap()

        if bootstrap_result.success:
            pid = self._launchctl.get_pid()
            return ProcessResult(
                success=True,
                message="Daemon started via launchctl",
                pid=pid,
            )
        else:
            # If bootstrap fails, try the legacy load command
            load_result = self._launchctl.load()
            if load_result.success:
                start_result = self._launchctl.start()
                pid = self._launchctl.get_pid()
                return ProcessResult(
                    success=start_result.success,
                    message=start_result.message,
                    pid=pid,
                )
            else:
                return ProcessResult(
                    success=False,
                    message=f"Failed to load launch agent: {load_result.message}",
                )

    def _stop_with_launchctl(self) -> ProcessResult:
        """Stop process using launchctl on macOS.

        Returns:
            ProcessResult indicating success or failure
        """
        # Try modern bootout first
        bootout_result = self._launchctl.bootout()

        if bootout_result.success:
            return ProcessResult(
                success=True,
                message="Daemon stopped and unloaded via launchctl",
            )

        # Fall back to stop + unload
        stop_result = self._launchctl.stop()
        unload_result = self._launchctl.unload()

        if stop_result.success or unload_result.success:
            return ProcessResult(
                success=True,
                message="Daemon stopped via launchctl",
            )
        else:
            return ProcessResult(
                success=False,
                message=f"Failed to stop daemon: {stop_result.message}",
            )

    def _start_with_subprocess(
        self,
        program_arguments: list[str] | None = None,
        working_directory: str | None = None,
        stdout_path: str | None = None,
        stderr_path: str | None = None,
        environment_variables: dict[str, str] | None = None,
    ) -> ProcessResult:
        """Start process using subprocess (non-macOS fallback).

        Args:
            program_arguments: Additional arguments for the program
            working_directory: Working directory for the process
            stdout_path: Path for stdout log file
            stderr_path: Path for stderr log file
            environment_variables: Environment variables for the process

        Returns:
            ProcessResult indicating success or failure
        """
        try:
            cmd = [self.program_path]  # type: ignore
            if program_arguments:
                cmd.extend(program_arguments)

            # Setup environment
            env = os.environ.copy()
            if environment_variables:
                env.update(environment_variables)

            # Setup stdout/stderr
            stdout = subprocess.DEVNULL
            stderr = subprocess.DEVNULL

            if stdout_path:
                stdout = open(stdout_path, "a")  # noqa: SIM115
            if stderr_path:
                stderr = open(stderr_path, "a")  # noqa: SIM115

            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=stdout,
                stderr=stderr,
                cwd=working_directory,
                env=env,
                start_new_session=True,
            )

            # Write PID file
            self.pid_file.parent.mkdir(parents=True, exist_ok=True)
            self.pid_file.write_text(str(process.pid))

            return ProcessResult(
                success=True,
                message=f"Daemon started with PID {process.pid}",
                pid=process.pid,
            )

        except OSError as e:
            return ProcessResult(
                success=False,
                message=f"Failed to start daemon: {e}",
            )

    def _stop_with_signal(self) -> ProcessResult:
        """Stop process using SIGTERM signal.

        Returns:
            ProcessResult indicating success or failure
        """
        pid = self._get_pid_from_file()

        if pid is None:
            return ProcessResult(
                success=False,
                message="Daemon is not running (no PID file)",
            )

        try:
            os.kill(pid, signal.SIGTERM)

            # Remove PID file
            if self.pid_file.exists():
                self.pid_file.unlink()

            return ProcessResult(
                success=True,
                message=f"Daemon stopped (PID {pid})",
                pid=pid,
            )

        except ProcessLookupError:
            # Process already dead, clean up PID file
            if self.pid_file.exists():
                self.pid_file.unlink()
            return ProcessResult(
                success=True,
                message="Daemon was not running",
            )

        except PermissionError:
            return ProcessResult(
                success=False,
                message=f"Permission denied to stop process {pid}",
                pid=pid,
            )

    def _is_running_via_pid(self) -> bool:
        """Check if process is running via PID file.

        Returns:
            True if process is running
        """
        pid = self._get_pid_from_file()
        if pid is None:
            return False

        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _get_pid_from_file(self) -> int | None:
        """Get PID from PID file.

        Returns:
            PID if file exists and is valid, None otherwise
        """
        if not self.pid_file.exists():
            return None

        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def _convert_launchctl_result(self, result: LaunchctlResult) -> ProcessResult:
        """Convert LaunchctlResult to ProcessResult.

        Args:
            result: LaunchctlResult to convert

        Returns:
            Equivalent ProcessResult
        """
        return ProcessResult(
            success=result.success,
            message=result.message,
        )
