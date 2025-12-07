from typing import Protocol


class Chunker(Protocol):
    def chunk(self, document: str) -> list[str]:
        ...

