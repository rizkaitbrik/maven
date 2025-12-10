import fnmatch
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from indexer.extraction.models.extraction_result import ExtractionResult


class TextExtractor:
    """Extracts content from plain text files.

    Uses LangChain's TextLoader for consistency with CodeExtractor.
    """

    def __init__(
            self,
            extensions: set[str] | None = None,
            patterns: list[str] | None = None,
            encoding: str = "utf-8",
    ):
        self._extensions = {ext.lower() for ext in (extensions or set())}
        self._patterns = patterns or []
        self._encoding = encoding

    @property
    def name(self) -> str:
        return "TextExtractor"

    def supports(self, file_path: Path | str) -> bool:
        path = Path(file_path)
        filename = path.name
        suffix = path.suffix.lower()

        if suffix and suffix in self._extensions:
            return True

        for pattern in self._patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return True

        return False

    def extract(self, file_path: Path | str) -> ExtractionResult:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not path.is_file():
            raise ValueError(f"Not a file: {path}")

        # Use LangChain's TextLoader
        loader = TextLoader(str(path), encoding=self._encoding)

        try:
            documents = loader.load()
            content = documents[0].page_content if documents else ""
        except Exception:
            # Fallback to manual reading with encoding fallback
            content = self._read_file_fallback(path)

        return ExtractionResult(
            text=content,
            metadata={
                "extractor": self.name,
                "path": str(path.resolve()),
                "filename": path.name,
                "extension": path.suffix,
                "encoding": self._encoding,
            },
        )

    def _read_file_fallback(self, path: Path) -> str:
        """Fallback if TextLoader fails."""
        for encoding in [self._encoding, "utf-8", "latin-1"]:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="latin-1", errors="replace")