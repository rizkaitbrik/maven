"""Code extractor using LangChain's LanguageParser for AST parsing."""

import fnmatch
from pathlib import Path

from langchain_community.document_loaders.parsers import LanguageParser
from langchain_core.documents import Document
from langchain_text_splitters import Language

from indexer.extraction.models import ExtractionResult

# Map our language names to LangChain's Language enum
LANGUAGE_MAP: dict[str, Language] = {
    "python": Language.PYTHON,
    "javascript": Language.JS,
    "typescript": Language.TS,
    "java": Language.JAVA,
    "kotlin": Language.KOTLIN,
    "go": Language.GO,
    "rust": Language.RUST,
    "ruby": Language.RUBY,
    "php": Language.PHP,
    "cpp": Language.CPP,
    "c": Language.C,
    "csharp": Language.CSHARP,
    "scala": Language.SCALA,
    "swift": Language.SWIFT,
    "lua": Language.LUA,
    "perl": Language.PERL,
    "haskell": Language.HASKELL,
    "elixir": Language.ELIXIR,
    "cobol": Language.COBOL,
    "markdown": Language.MARKDOWN,
    "latex": Language.LATEX,
    "html": Language.HTML,
    "protobuf": Language.PROTO,
    "restructuredtext": Language.RST,
    "solidity": Language.SOL,
}


class CodeExtractor:
    """Extracts content from source code files with AST parsing.

    Uses LangChain's LanguageParser (tree-sitter) for multi-language
    AST parsing. Supports 20+ programming languages.

    Usage:
        extractor = CodeExtractor(
            extensions={'.py', '.js'},
            filenames={'Makefile', 'Dockerfile'},
            patterns=['Dockerfile.*'],
            language_map={'.py': 'python', '.js': 'javascript'},
        )

        result = extractor.extract(path)
        print(result.metadata["language"])     # "python"
        print(result.metadata["segments"])     # List of code segments
    """

    def __init__(
        self,
        extensions: set[str] | None = None,
        filenames: set[str] | None = None,
        patterns: list[str] | None = None,
        language_map: dict[str, str] | None = None,
        encoding: str = "utf-8",
        parse_ast: bool = True,
        parser_threshold: int = 0,
    ):
        """Initialize the code extractor.

        Args:
            extensions: Set of extensions (e.g., {'.py', '.js'})
            filenames: Set of exact filenames (e.g., {'Makefile', 'Dockerfile'})
            patterns: List of glob patterns (e.g., ['Dockerfile.*'])
            language_map: Map extension/filename to language name
            encoding: Default encoding for reading files
            parse_ast: Whether to parse AST for supported languages
            parser_threshold: Minimum lines to activate parsing (0 = always)
        """
        self._extensions = {ext.lower() for ext in (extensions or set())}
        self._filenames = filenames or set()
        self._patterns = patterns or []
        self._language_map = language_map or {}
        self._encoding = encoding
        self._parse_ast = parse_ast
        self._parser_threshold = parser_threshold

    @property
    def name(self) -> str:
        return "CodeExtractor"

    def supports(self, file_path: Path | str) -> bool:
        """Check if file is supported."""
        path = Path(file_path)
        filename = path.name
        suffix = path.suffix.lower()

        if suffix and suffix in self._extensions:
            return True

        if filename in self._filenames:
            return True

        for pattern in self._patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return True

        return False

    def detect_language(self, file_path: Path | str) -> str | None:
        """Detect programming language from file."""
        path = Path(file_path)
        filename = path.name
        suffix = path.suffix.lower()

        return (
            self._language_map.get(suffix) or
            self._language_map.get(filename) or
            self._language_map.get(filename.lower())
        )

    def extract(self, file_path: Path | str) -> ExtractionResult:
        """Extract content from a code file.

        Args:
            file_path: Path to the file

        Returns:
            ExtractionResult with code content and AST segments

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If path is not a file
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not path.is_file():
            raise ValueError(f"Not a file: {path}")

        content = self._read_file(path)
        language = self.detect_language(path)

        metadata = {
            "extractor": self.name,
            "path": str(path.resolve()),
            "filename": path.name,
            "extension": path.suffix,
            "language": language,
            "encoding": self._encoding,
        }

        # Parse AST if supported
        if self._parse_ast and language:
            segments = self._parse_code(content, language)
            if segments:
                metadata["segments"] = segments
                metadata["segment_count"] = len(segments)

        return ExtractionResult(text=content, metadata=metadata)

    def _parse_code(self, source: str, language: str) -> list[dict] | None:
        """Parse code into segments using LangChain's LanguageParser."""
        lc_language = LANGUAGE_MAP.get(language)
        if not lc_language:
            return None

        try:
            parser = LanguageParser(
                language=lc_language,
                parser_threshold=self._parser_threshold,
            )

            # Create a blob-like object for the parser
            from langchain_core.document_loaders import Blob
            blob = Blob.from_data(source, path=f"code.{language}")

            # Parse and convert to dicts
            documents: list[Document] = list(parser.lazy_parse(blob))

            segments = []
            for doc in documents:
                segments.append({
                    "content": doc.page_content,
                    "content_type": doc.metadata.get("content_type"),
                    "language": language,
                })

            return segments

        except Exception:
            # If parsing fails, return None (raw text still available)
            return None

    def _read_file(self, path: Path) -> str:
        """Read file with encoding fallback."""
        try:
            return path.read_text(encoding=self._encoding)
        except UnicodeDecodeError:
            pass

        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except UnicodeDecodeError:
            pass

        return path.read_text(encoding="latin-1")