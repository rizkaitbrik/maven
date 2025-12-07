from collections.abc import Mapping
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    meta: Mapping[str, Any]
    start: int | None = None
    end: int | None = None
