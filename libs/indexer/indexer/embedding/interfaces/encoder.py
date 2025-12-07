from typing import Protocol


class encoder(Protocol):
    def encode(self, text: str) -> list[float]:
        ...