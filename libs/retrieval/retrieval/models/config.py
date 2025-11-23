from dataclasses import dataclass, field
from pathlib import Path, PurePath
from fnmatch import fnmatch


@dataclass
class RetrieverConfig:
    """Retriever configuration."""
    root: str = field(default=str(Path.home()))
    index_path: str = field(default="index.json")
    allowed_list: list[str] = field(default_factory=list)
    block_list: list[str] = field(default_factory=list)
    text_extensions: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.root = Path(self.root)
        self.index_path = self.root / self.index_path
        # Keep patterns as strings for glob matching

    def _matches_pattern(self, path: Path | str, pattern: str) -> bool:
        """Check if path matches the given pattern."""
        path_str = str(path) if isinstance(path, Path) else path
        path_obj = Path(path_str)
        
        # If pattern is an absolute path (directory), check if path is within it
        if not any(c in pattern for c in ['*', '?', '[', ']']):
            # It's a plain directory path
            try:
                pattern_path = Path(pattern).expanduser().resolve()
                path_resolved = path_obj.expanduser().resolve()
                return path_resolved.is_relative_to(pattern_path)
            except (ValueError, AttributeError, OSError):
                pass
        
        # Handle glob patterns
        # Convert pattern to work with fnmatch
        # Pattern like "**/node_modules/**" should match any path containing node_modules
        if pattern.startswith('**/'):
            # Remove leading **/ and check if pattern exists anywhere in path
            pattern_without_prefix = pattern[3:]
            
            # If pattern ends with /**, it means "this directory and everything under it"
            if pattern_without_prefix.endswith('/**'):
                dir_name = pattern_without_prefix[:-3]
                # Check if this directory name appears in the path
                return f'/{dir_name}/' in f'/{path_str}/' or path_str.endswith(f'/{dir_name}')
            else:
                # Match the pattern anywhere in the path
                return fnmatch(path_str, f'*/{pattern_without_prefix}') or \
                       fnmatch(path_str, pattern_without_prefix)
        
        # Use PurePath.match for other patterns (works from right to left)
        return PurePath(path_str).match(pattern)

    def is_allowed(self, path: Path | str) -> bool:
        """Check if path matches any pattern in the allowed list."""
        if not self.allowed_list:
            return True  # If no allowed list, all paths are allowed
        
        for pattern in self.allowed_list:
            if self._matches_pattern(path, pattern):
                return True
                
        return False

    def is_blocked(self, path: Path | str) -> bool:
        """Check if path matches any pattern in the block list."""
        if not self.block_list:
            return False
        
        for pattern in self.block_list:
            if self._matches_pattern(path, pattern):
                return True
                
        return False