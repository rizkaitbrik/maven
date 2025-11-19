import asyncio
import subprocess
from pathlib import Path
from retrieval.interfaces.retriever import Retriever
from retrieval.models.search import SearchResult, SearchResponse, SearchRequest


class SpotlightAdapter:
    """macOS Spotlight retriever via mdfind."""

    def __init__(self, root: Path | None = None):
        self.root = root or Path.home()

    async def search(self, request: SearchRequest) -> SearchResponse:
        offset = (request.page - 1) * request.size
        limit = offset + request.size

        cmd = [
            "mdfind",
            "-onlyin", str(self.root),
            request.query  # No -limit flag, just the query
        ]

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

        # Apply pagination in Python
        total = len(paths)
        paginated = paths[offset:offset + request.size]

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