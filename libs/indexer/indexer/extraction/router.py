from pathlib import Path
from typing import Protocol

from indexer.extraction.models.extraction_result import ExtractionResult


class Extractor(Protocol):
    """Protocol for extractors."""

    def extract(self, file_path: Path | str) -> ExtractionResult: ...
    def supports(self, file_path: Path | str) -> bool: ...

    @property
    def name(self) -> str: ...


class ExtractionRouter:
    """Routes files to the appropriate extractor.

    The router maintains a registry of extractors and delegates
    extraction based on file extension, filename, or pattern.

    Usage:
        router = ExtractionRouter()
        router.register(TextExtractor(extensions={'.txt'}))
        router.register(CodeExtractor(extensions={'.py'}))

        result = router.extract(Path("main.py"))
    """

    def __init__(self):
        """Initialize an empty router."""
        self._extractors: list[Extractor] = []

    def register(self, extractor: Extractor) -> "ExtractionRouter":
        """Register an extractor.

        Args:
            extractor: Extractor instance

        Returns:
            Self for chaining
        """
        self._extractors.append(extractor)
        return self

    def unregister(self, extractor: Extractor) -> "ExtractionRouter":
        """Unregister an extractor.

        Args:
            extractor: Extractor instance to remove

        Returns:
            Self for chaining
        """
        if extractor in self._extractors:
            self._extractors.remove(extractor)
        return self

    def get_extractor(self, file_path: Path | str) -> Extractor | None:
        """Get the appropriate extractor for a file.

        Args:
            file_path: File path

        Returns:
            Extractor or None if no match
        """
        path = Path(file_path)

        for extractor in self._extractors:
            if extractor.supports(path):
                return extractor

        return None

    def supports(self, file_path: Path | str) -> bool:
        """Check if any extractor supports this file."""
        return self.get_extractor(file_path) is not None

    def extract(self, file_path: Path | str) -> ExtractionResult:
        """Extract content from a file.

        Args:
            file_path: File path

        Returns:
            ExtractionResult

        Raises:
            ValueError: If no extractor found for file
        """
        path = Path(file_path)
        extractor = self.get_extractor(path)

        if extractor is None:
            raise ValueError(f"No extractor registered for: {path.name}")

        return extractor.extract(path)

    def extract_safe(self, file_path: Path | str) -> ExtractionResult | None:
        """Extract content, returning None on failure."""
        try:
            return self.extract(file_path)
        except (ValueError, FileNotFoundError):
            return None

    @property
    def extractors(self) -> list[Extractor]:
        """Get registered extractors."""
        return list(self._extractors)