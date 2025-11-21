from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RetrieverConfig:
    """Retriever configuration."""
    root: str = field(default=str(Path.home()))
    index_path: str = field(default="index.json")
    allow_list: list[str] = field(default_factory=list)
    block_list: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.root = Path(self.root)
        self.index_path = self.root / self.index_path
        self.allow_list = [Path(p) for p in self.allow_list]
        self.block_list = [Path(p) for p in self.block_list]

    def is_allowed(self, path: Path) -> bool:
        return any(path.match(pattern) for pattern in self.allow_list)

    def is_blocked(self, path: Path) -> bool:
        return any(path.match(pattern) for pattern in self.block_list)