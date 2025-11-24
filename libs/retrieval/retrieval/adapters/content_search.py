"""Content-based search adapter for searching inside files."""

import re
from pathlib import Path

from retrieval.models.config import RetrieverConfig
from retrieval.models.search import (
    MatchType,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from retrieval.services.content_extractor import ContentExtractor


class ContentMatch:
    """Represents a match found in file content."""
    
    def __init__(self, path: Path, line_number: int, line_content: str, score: float = 1.0):
        self.path = path
        self.line_number = line_number
        self.line_content = line_content
        self.score = score


class ContentSearchAdapter:
    """Search file contents using regex patterns."""

    def __init__(self, root: Path | None = None, config: RetrieverConfig | None = None):
        """Initialize content search adapter.
        
        Args:
            root: Root directory to search from
            config: Retriever configuration for filtering
        """
        self.root = root or Path.home()
        self.config = config or RetrieverConfig()
        
        # Use text_extensions from config (must be provided by config)
        self.extractor = ContentExtractor(text_extensions=self.config.text_extensions)

    def _get_search_paths(self) -> list[Path]:
        """Get list of directories to search based on config.
        
        Returns:
            List of Path objects to search in
        """
        if self.config.allowed_list:
            # Extract real directory paths (not glob patterns)
            paths = []
            for pattern in self.config.allowed_list:
                # Skip glob patterns - we'll use them for filtering later
                if not any(c in pattern for c in ['*', '?', '[', ']']):
                    path = Path(pattern).expanduser().resolve()
                    if path.exists() and path.is_dir():
                        paths.append(path)
            
            # If no real directories found, search from root
            if not paths:
                paths = [self.root]
                
            return paths
        else:
            return [self.root]

    def _should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed based on config filtering.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file should be processed
        """
        file_str = str(file_path)
        
        # Check if blocked
        if self.config.is_blocked(file_str):
            return False
        
        # Check if allowed
        if not self.config.is_allowed(file_str):
            return False
        
        # Check if it's a text file
        return self.extractor.is_text_file(file_path)

    def _walk_directory(self, root: Path) -> list[Path]:
        """Recursively walk directory and yield files that pass filtering.
        
        Args:
            root: Root directory to walk
            
        Yields:
            Path objects for files to process
        """
        files = []
        
        try:
            for item in root.rglob('*'):
                # Skip if not a file
                if not item.is_file():
                    continue
                
                # Apply filtering
                if self._should_process_file(item):
                    files.append(item)
                    
        except (PermissionError, OSError):
            # Skip directories we can't access
            pass
        
        return files

    def _search_in_file(self, file_path: Path, pattern: str, case_sensitive: bool = False) -> list[ContentMatch]:
        """Search for pattern in a single file.
        
        Args:
            file_path: Path to file to search
            pattern: Regex pattern to search for
            case_sensitive: Whether search should be case-sensitive
            
        Returns:
            List of ContentMatch objects for matches found
        """
        matches = []
        
        # Extract file content
        extracted = self.extractor.extract(file_path)
        if not extracted.success:
            return matches
        
        # Compile regex pattern
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
        except re.error:
            # Invalid regex, treat as literal string
            regex = re.compile(re.escape(pattern), re.IGNORECASE if not case_sensitive else 0)
        
        # Search through lines
        for line_num, line_content in enumerate(extracted.lines, start=1):
            if regex.search(line_content):
                # Calculate score (simple: earlier matches score higher)
                score = 1.0 - (line_num / max(len(extracted.lines), 1)) * 0.5
                matches.append(ContentMatch(
                    path=file_path,
                    line_number=line_num,
                    line_content=line_content,
                    score=score
                ))
        
        return matches

    def _create_snippet(self, lines: list[str], match_line_num: int, context_lines: int = 3) -> str:
        """Create a snippet with context around the matching line.
        
        Args:
            lines: All lines from the file
            match_line_num: Line number of match (1-indexed)
            context_lines: Number of lines to include before/after match
            
        Returns:
            Formatted snippet with context
        """
        # Convert to 0-indexed
        match_idx = match_line_num - 1
        
        # Get range with context
        start_idx = max(0, match_idx - context_lines)
        end_idx = min(len(lines), match_idx + context_lines + 1)
        
        # Build snippet
        snippet_lines = []
        for idx in range(start_idx, end_idx):
            line_num = idx + 1
            prefix = "→ " if idx == match_idx else "  "
            snippet_lines.append(f"{prefix}L{line_num}: {lines[idx]}")
        
        return "\n".join(snippet_lines)

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Search file contents for the given query.
        
        Args:
            request: Search request with query and pagination
            
        Returns:
            SearchResponse with matching results
        """
        # Get directories to search
        search_paths = self._get_search_paths()
        
        # Collect all matches from all files
        all_matches: list[ContentMatch] = []
        
        for search_path in search_paths:
            # Get all files to process
            files = self._walk_directory(search_path)
            
            # Search each file
            for file_path in files:
                file_matches = self._search_in_file(file_path, request.query, case_sensitive=False)
                all_matches.extend(file_matches)
        
        # Sort by score (highest first)
        all_matches.sort(key=lambda m: m.score, reverse=True)
        
        # Calculate pagination
        total = len(all_matches)
        offset = (request.page - 1) * request.size
        paginated_matches = all_matches[offset:offset + request.size]
        
        # Convert matches to SearchResults
        results = []
        for match in paginated_matches:
            # Extract content for snippet
            extracted = self.extractor.extract(match.path)
            snippet = ""
            if extracted.success:
                snippet = self._create_snippet(extracted.lines, match.line_number)
            
            results.append(SearchResult(
                path=str(match.path),
                score=match.score,
                snippet=snippet,
                line_number=match.line_number,
                match_type=MatchType.CONTENT,
                metadata={
                    'line_content': match.line_content.strip()
                }
            ))
        
        return SearchResponse(
            query=request.query,
            page=request.page,
            size=request.size,
            total=total,
            results=results
        )

