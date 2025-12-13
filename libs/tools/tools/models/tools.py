from dataclasses import dataclass, field
from typing import Optional, Mapping, Any, Dict
from enum import Enum


class ToolType(str, Enum):
    DEVELOPMENT = "development"
    SEARCH = "search"
    ANALYSIS = "analysis"
    DATA = "data"
    PRODUCTIVITY = "productivity"
    OTHER = "other"


@dataclass
class ToolConfig:
    enabled: bool = True
    auth: Optional[Mapping[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


@dataclass
class ToolMetadata:
    category: ToolType
    requires_auth: bool = False
    auth_env_vars: list[str] = field(default_factory=list)
    cost_estimate: Optional[str] = None  # e.g., "free", "paid", "$0.01/call"
    rate_limit: Optional[str] = None  # e.g., "100/hour"
    version: str = "1.0.0"
