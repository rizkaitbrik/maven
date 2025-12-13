from dataclasses import dataclass


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