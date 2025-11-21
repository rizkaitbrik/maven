import asyncio
import subprocess
from pathlib import Path
from retrieval.interfaces.retriever import Retriever
from retrieval.models.search import SearchResult, SearchResponse, SearchRequest
from retrieval.models.config import RetrieverConfig


class SpotlightAdapter:
    """macOS Spotlight retriever via mdfind."""

    def __init__(self, root: Path | None = None, config: RetrieverConfig | None = None):
        self.root = root or Path.home()
        self.config = config or RetrieverConfig()

    def _filter_paths(self, paths: list[Path]) -> list[Path]:
        return [p for p in paths if self.config.is_allowed(p) \
            and not self.config.is_blocked(p)]

    async def search(self, request: SearchRequest) -> SearchResponse:
        offset = (request.page - 1) * request.size
        limit = offset + request.size
        config = request.config or self.config

        cmd = ["mdfind"]

        if config.allow_list:
            for p in range(len(config.allow_list)):
                cmd.extend(["-onlyin", str(config.allow_list[p])])
        else:
            cmd.extend(["-onlyin", str(self.root)])

        cmd.append(f'"{request.query}"')

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

        filtered_paths = self._filter_paths(paths)
        total = len(filtered_paths)
        paginated = filtered_paths[offset:offset + request.size]

        results = [
            SearchResult(
                path=str(p),
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