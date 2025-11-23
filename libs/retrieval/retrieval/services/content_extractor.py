"""Service for extracting text content from files."""

from pathlib import Path
from typing import NamedTuple
import chardet


class ExtractedContent(NamedTuple):
    """Represents extracted content from a file."""
    path: Path
    content: str
    encoding: str
    lines: list[str]
    success: bool
    error: str | None = None


class ContentExtractor:
    """Extract text content from various file types.
    
    This service is config-driven. File extensions must be provided
    via the text_extensions parameter, typically from RetrieverConfig.
    """

    # Maximum file size to process (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    def __init__(
        self,
        text_extensions: list[str] | set[str],
        max_file_size: int | None = None
    ):
        """Initialize content extractor.
        
        Args:
            text_extensions: List/set of file extensions to treat as text (required)
            max_file_size: Maximum file size in bytes to process (default: 10MB)
        """
        self.max_file_size = max_file_size or self.MAX_FILE_SIZE
        
        # Ensure all extensions start with a dot
        self.text_extensions = {
            ext if ext.startswith('.') else f'.{ext}'
            for ext in text_extensions
        }

    def is_text_file(self, path: Path) -> bool:
        """Check if a file is likely a text file based on extension.
        
        Args:
            path: Path to the file
            
        Returns:
            True if file extension indicates text content
        """
        # Check extension
        if path.suffix.lower() in self.text_extensions:
            return True
        
        # Files without extension but common text file names
        if path.name.lower() in {
            'readme', 'license', 'makefile', 'dockerfile',
            'changelog', 'authors', 'contributors', 'todo',
        }:
            return True
        
        return False

    def _detect_encoding(self, file_path: Path, sample_size: int = 8192) -> str:
        """Detect file encoding.
        
        Args:
            file_path: Path to the file
            sample_size: Number of bytes to sample for detection
            
        Returns:
            Detected encoding name
        """
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(sample_size)
            
            # Use chardet for encoding detection
            result = chardet.detect(raw_data)
            encoding = result.get('encoding', 'utf-8')
            
            # Fallback to utf-8 if detection fails
            if not encoding or result.get('confidence', 0) < 0.5:
                encoding = 'utf-8'
                
            return encoding
            
        except Exception:
            return 'utf-8'

    def extract(self, path: Path) -> ExtractedContent:
        """Extract text content from a file.
        
        Args:
            path: Path to the file
            
        Returns:
            ExtractedContent with file contents and metadata
        """
        # Check if file exists
        if not path.exists():
            return ExtractedContent(
                path=path,
                content='',
                encoding='',
                lines=[],
                success=False,
                error='File does not exist'
            )

        # Check if it's a file (not directory)
        if not path.is_file():
            return ExtractedContent(
                path=path,
                content='',
                encoding='',
                lines=[],
                success=False,
                error='Not a file'
            )

        # Check file size
        try:
            file_size = path.stat().st_size
            if file_size > self.max_file_size:
                return ExtractedContent(
                    path=path,
                    content='',
                    encoding='',
                    lines=[],
                    success=False,
                    error=f'File too large ({file_size} bytes > {self.max_file_size} bytes)'
                )
        except OSError as e:
            return ExtractedContent(
                path=path,
                content='',
                encoding='',
                lines=[],
                success=False,
                error=f'Cannot access file: {e}'
            )

        # Check if likely text file
        if not self.is_text_file(path):
            return ExtractedContent(
                path=path,
                content='',
                encoding='',
                lines=[],
                success=False,
                error='Not a recognized text file type'
            )

        # Detect encoding
        encoding = self._detect_encoding(path)

        # Try to read the file with detected encoding
        try:
            with open(path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()
                lines = content.splitlines()
            
            return ExtractedContent(
                path=path,
                content=content,
                encoding=encoding,
                lines=lines,
                success=True,
                error=None
            )
            
        except UnicodeDecodeError:
            # Try with utf-8 as fallback
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    lines = content.splitlines()
                
                return ExtractedContent(
                    path=path,
                    content=content,
                    encoding='utf-8',
                    lines=lines,
                    success=True,
                    error=None
                )
            except Exception as e:
                return ExtractedContent(
                    path=path,
                    content='',
                    encoding='',
                    lines=[],
                    success=False,
                    error=f'Encoding error: {e}'
                )
                
        except Exception as e:
            return ExtractedContent(
                path=path,
                content='',
                encoding='',
                lines=[],
                success=False,
                error=f'Read error: {e}'
            )

    def extract_with_line_numbers(self, path: Path) -> list[tuple[int, str]]:
        """Extract file content with line numbers.
        
        Args:
            path: Path to the file
            
        Returns:
            List of (line_number, line_content) tuples (1-indexed)
        """
        result = self.extract(path)
        if not result.success:
            return []
        
        return [(i + 1, line) for i, line in enumerate(result.lines)]

