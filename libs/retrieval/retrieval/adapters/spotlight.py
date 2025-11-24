import asyncio
from pathlib import Path

from retrieval.models.config import RetrieverConfig
from retrieval.models.search import SearchRequest, SearchResponse, SearchResult


class SpotlightAdapter:
    """macOS Spotlight retriever via mdfind."""

    def __init__(self, root: Path | None = None, config: RetrieverConfig | None = None):
        self.root = root or Path.home()
        self.config = config or RetrieverConfig()

    def _filter_paths(self, paths: list[str]) -> list[str]:
        """Filter paths based on allowed and block lists."""
        return [
            p for p in paths 
            if self.config.is_allowed(p) and not self.config.is_blocked(p)
        ]

    async def search(self, request: SearchRequest) -> SearchResponse:
        offset = (request.page - 1) * request.size
        config = request.config or self.config

        cmd = ["mdfind"]

        # Use allowed_list from config if specified, otherwise search in root
        # Filter out glob patterns - mdfind only accepts real directories
        if config.allowed_list:
            real_dirs = [p for p in config.allowed_list if not any(c in p for c in ['*', '?', '[', ']'])]
            if real_dirs:
                for allowed_path in real_dirs:
                    cmd.extend(["-onlyin", str(allowed_path)])
            else:
                # If only glob patterns, search from root and filter later
                cmd.extend(["-onlyin", str(self.root)])
        else:
            cmd.extend(["-onlyin", str(self.root)])

        cmd.append(request.query)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)

        if proc.returncode != 0:
            paths = []
        else:
            paths = [p for p in stdout.decode().strip().split('\n') if p]

        # Apply filtering after getting all results
        filtered_paths = self._filter_paths(paths)
        total = len(filtered_paths)
        
        # Apply pagination
        paginated = filtered_paths[offset:offset + request.size]

        results = [
            SearchResult(
                path=p,
                score=1.0 - (i / total) if total > 0 else 1.0,
                metadata=None
            )
            for i, p in enumerate(paginated, start=offset)
        ]

        return SearchResponse(
            query=request.query,
            page=request.page,
            size=request.size,
            total=total,
            results=results
        )