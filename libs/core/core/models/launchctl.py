from dataclasses import dataclass, field


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
