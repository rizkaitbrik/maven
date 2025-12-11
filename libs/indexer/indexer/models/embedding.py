from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Embedding:
    vector: list[float]
    model: Optional[str] = None
    dims: int | None = None
    id: str | None = None
    meta: Optional[Mapping[str, Any]] = None
    