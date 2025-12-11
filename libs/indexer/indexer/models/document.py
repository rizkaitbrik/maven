from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass
class Document:
    text: str
    meta: Mapping[str, Any]