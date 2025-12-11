from pathlib import Path
from typing import Protocol

from indexer.extraction.models.extraction_result import ExtractionResult


class Extractor(Protocol):
    def extract(self, file_path: Path | str) -> ExtractionResult:
        ...

    def supports(self, file_path: Path | str) -> bool:
        ...

    @property
    def name(self) -> str:
        ...