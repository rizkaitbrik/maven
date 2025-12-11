from dataclasses import dataclass
from typing import Any


@dataclass
class ExtractionResult:
    text: str
    # TODO: Add images and tables
    metadata: dict[str, Any]