import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Chunk:
    id: str
    content: str
    doc_id: str
    index: int
    metadata: Mapping[str, Any]=field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.content)

    @property
    def size_bytes(self) -> int:
        return len(self.content.encode("utf-8"))

    @property
    def page_number(self) -> int:
        return self.index + 1

    @property
    def word_count(self):
        return len(self.content.split())

    @staticmethod
    def generate_id(doc_id: str, index: int) -> str:
        raw = f"{doc_id}:chunk:{index}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

@dataclass
class ChunkingConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 150
    min_chunk_size: int = 100
    max_chunk_size: int = 2000
    use_ast_chunks: bool = True
    separators: list[str] = field(default_factory=lambda: [
        "\n\n",     # Paragraphs
        "\n",       # Lines
        ". ",       # Sentences
        ", ",       # Clauses
        " ",        # Words
    ])