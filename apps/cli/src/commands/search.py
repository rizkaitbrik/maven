import asyncio
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from retrieval.adapters.spotlight import SpotlightAdapter
from retrieval.models.search import SearchRequest

console = Console()

def search(
    query: str = typer.Argument(..., help="Search query"),
    root: str = typer.Option(str(Path.home()), help="Search root directory"),
    limit: int = typer.Option(10, help="Max results"),
    page: int = typer.Option(1, help="Page number"),
    json: bool = typer.Option(False, help="Output as JSON")
):
    """Search files using platform-native indexing."""
    adapter = SpotlightAdapter(Path(root))
    request = SearchRequest(query=query, page=page, size=limit)

    response = asyncio.run(adapter.search(request))

    if json:
        import json as json_lib
        print(json_lib.dumps({
            "total": response.total,
            "results": [{"path": r.path, "score": r.score} for r in response.results]
        }, indent=2))
    else:
        table = Table(title=f"'{query}' ({response.total} total)")
        table.add_column("Path", style="cyan", no_wrap=False)
        table.add_column("Score", justify="right", style="magenta")

        for r in response.results:
            table.add_row(r.path, f"{r.score:.3f}")

        console.print(table)