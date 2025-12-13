from dataclasses import dataclass


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