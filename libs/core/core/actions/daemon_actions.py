"""Daemon management actions."""

from dataclasses import dataclass
from pathlib import Path

import grpc

from core import maven_pb2, maven_pb2_grpc
from core.process_manager import ProcessController


@dataclass
class DaemonStatus:
    """Daemon status information.

    Attributes:
        running: Whether the daemon is running
        pid: Process ID if running
        uptime: Human-readable uptime string
        indexing: Whether indexing is active
        watcher_active: Whether the file watcher is active
        files_indexed: Number of files indexed
    """

    running: bool
    pid: int | None = None
    uptime: str = ""
    indexing: bool = False
    watcher_active: bool = False
    files_indexed: int = 0


@dataclass
class ActionResult:
    """Result from an action.

    Attributes:
        success: Whether the action succeeded
        message: Human-readable message about the result
        data: Optional additional data
    """

    success: bool
    message: str
    data: dict | None = None


class DaemonActions:
    """Encapsulates daemon management business logic.

    This class provides high-level operations for managing the Maven daemon,
    abstracting away the details of gRPC communication and process management.
    """

    def __init__(
        self,
        grpc_host: str = "127.0.0.1",
        grpc_port: int = 50051,
        state_dir: Path | None = None,
        daemon_module: str = "daemon.main",
    ):
        """Initialize daemon actions.

        Args:
            grpc_host: Host for gRPC communication
            grpc_port: Port for gRPC communication
            state_dir: Directory for daemon state files
            daemon_module: Python module path for daemon entry point
        """
        self.grpc_host = grpc_host
        self.grpc_port = grpc_port
        self.state_dir = state_dir or Path.home() / ".maven"
        self.daemon_module = daemon_module

        # Initialize process controller
        self._process_controller = ProcessController(
            label="com.maven.daemon",
            pid_file=self.state_dir / "daemon.pid",
        )

    def start(self, detach: bool = True, use_launchctl: bool = True) -> ActionResult:
        """Start the Maven daemon.

        Args:
            detach: Whether to run as background process
            use_launchctl: Whether to use launchctl on macOS

        Returns:
            ActionResult indicating success or failure
        """
        # Check if already running
        if self.is_running():
            pid = self.get_pid()
            return ActionResult(
                success=False,
                message=f"Daemon already running (PID: {pid})",
            )

        import sys

        # Determine program path
        program_path = sys.executable
        program_arguments = ["-m", self.daemon_module]

        # Set up log paths
        log_dir = self.state_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = str(log_dir / "daemon.stdout.log")
        stderr_path = str(log_dir / "daemon.stderr.log")

        # Configure the process controller
        self._process_controller.program_path = program_path

        if detach:
            result = self._process_controller.start(
                program_arguments=program_arguments,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                use_launchctl=use_launchctl,
            )

            if result.success:
                return ActionResult(
                    success=True,
                    message="Daemon started in background",
                    data={"pid": result.pid},
                )
            else:
                return ActionResult(
                    success=False,
                    message=f"Failed to start daemon: {result.message}",
                )
        else:
            # Foreground mode - use subprocess directly
            import subprocess

            try:
                subprocess.run(
                    [program_path, *program_arguments],
                    check=False,
                )
                return ActionResult(
                    success=True,
                    message="Daemon exited",
                )
            except Exception as e:
                return ActionResult(
                    success=False,
                    message=f"Failed to run daemon: {e}",
                )

    def stop(self, use_launchctl: bool = True) -> ActionResult:
        """Stop the Maven daemon.

        Attempts to stop gracefully via gRPC first, then falls back to
        signal-based termination if necessary.

        Args:
            use_launchctl: Whether to use launchctl on macOS

        Returns:
            ActionResult indicating success or failure
        """
        if not self.is_running():
            return ActionResult(
                success=False,
                message="Daemon is not running",
            )

        # Try to shutdown gracefully via gRPC
        try:
            stub = self._get_grpc_stub()
            response = stub.Shutdown(maven_pb2.ShutdownRequest())

            if response.shutdown:
                return ActionResult(
                    success=True,
                    message="Daemon stopped gracefully",
                )
            else:
                # Fall back to process termination
                return self._force_stop(use_launchctl)

        except grpc.RpcError:
            # gRPC not available, fall back to process termination
            return self._force_stop(use_launchctl)

    def restart(self, use_launchctl: bool = True) -> ActionResult:
        """Restart the Maven daemon.

        Args:
            use_launchctl: Whether to use launchctl on macOS

        Returns:
            ActionResult indicating success or failure
        """
        self.stop(use_launchctl=use_launchctl)

        # Wait a moment for cleanup
        import time

        time.sleep(1)

        return self.start(detach=True, use_launchctl=use_launchctl)

    def status(self) -> DaemonStatus:
        """Get daemon status.

        Returns:
            DaemonStatus with current state information
        """
        # Check if process is running
        running = self.is_running()
        pid = self.get_pid()

        if not running:
            return DaemonStatus(running=False, pid=pid)

        # Try to get detailed status via gRPC
        try:
            stub = self._get_grpc_stub()
            response = stub.GetStatus(maven_pb2.StatusRequest())

            return DaemonStatus(
                running=response.running,
                pid=response.pid or pid,
                uptime=response.uptime,
                indexing=response.indexing,
                watcher_active=response.watcher_active,
                files_indexed=response.files_indexed,
            )

        except grpc.RpcError:
            # gRPC not available, return basic status
            return DaemonStatus(running=running, pid=pid)

    def ping(self) -> ActionResult:
        """Ping the daemon to check if it's alive.

        Returns:
            ActionResult indicating success or failure
        """
        try:
            stub = self._get_grpc_stub()
            response = stub.Ping(maven_pb2.PingRequest())

            if response.alive:
                return ActionResult(
                    success=True,
                    message=f"Daemon is alive (version: {response.version})",
                    data={"version": response.version},
                )
            else:
                return ActionResult(
                    success=False,
                    message="Daemon is not responding",
                )

        except grpc.RpcError as e:
            return ActionResult(
                success=False,
                message=f"Failed to ping daemon: {e}",
            )

    def is_running(self) -> bool:
        """Check if daemon is running.

        Returns:
            True if daemon is running
        """
        # First check via PID file
        from daemon.state import DaemonStateManager

        state_mgr = DaemonStateManager(self.state_dir)
        return state_mgr.is_running()

    def get_pid(self) -> int | None:
        """Get daemon PID.

        Returns:
            PID if running, None otherwise
        """
        from daemon.state import DaemonStateManager

        state_mgr = DaemonStateManager(self.state_dir)
        return state_mgr.get_pid()

    def get_log_path(self) -> Path:
        """Get the daemon log file path.

        Returns:
            Path to the log file
        """
        return self.state_dir / "logs" / "maven.daemon.log"

    def _get_grpc_stub(self) -> maven_pb2_grpc.DaemonServiceStub:
        """Get a gRPC stub for daemon communication.

        Returns:
            DaemonServiceStub instance
        """
        channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
        return maven_pb2_grpc.DaemonServiceStub(channel)

    def _force_stop(self, use_launchctl: bool = True) -> ActionResult:
        """Force stop the daemon via process termination.

        Args:
            use_launchctl: Whether to use launchctl on macOS

        Returns:
            ActionResult indicating success or failure
        """
        result = self._process_controller.stop(use_launchctl=use_launchctl)

        if result.success:
            return ActionResult(
                success=True,
                message="Daemon stopped via signal",
            )
        else:
            return ActionResult(
                success=False,
                message=f"Failed to stop daemon: {result.message}",
            )
