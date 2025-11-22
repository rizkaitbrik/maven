import asyncio
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from retrieval.adapters.spotlight import SpotlightAdapter
from retrieval.models.search import SearchRequest
from retrieval.services.config_manager import ConfigManager

console = Console()

def search(
    query: str = typer.Argument(..., help="Search query"),
    root: str = typer.Option(None, help="Search root directory (overrides config)"),
    limit: int = typer.Option(10, help="Max results per page"),
    page: int = typer.Option(1, help="Page number"),
    json: bool = typer.Option(False, help="Output as JSON")
):
    """Search files using platform-native indexing with config-based filtering."""
    
    # Load configuration from config file and environment
    try:
        config_manager = ConfigManager()
        config = config_manager.config
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load config: {e}[/yellow]")
        console.print("[yellow]Using default configuration...[/yellow]")
        from retrieval.models.config import RetrieverConfig
        config = RetrieverConfig()
    
    # Override root if specified via CLI
    if root:
        config.root = Path(root)
    
    adapter = SpotlightAdapter(config.root, config=config)
    request = SearchRequest(query=query, page=page, size=limit, config=config)

    response = asyncio.run(adapter.search(request))

    if json:
        import json as json_lib
        print(json_lib.dumps({
            "query": response.query,
            "page": response.page,
            "size": response.size,
            "total": response.total,
            "results": [{"path": r.path, "score": r.score} for r in response.results]
        }, indent=2))
    else:
        # Show pagination info
        total_pages = (response.total + limit - 1) // limit if limit > 0 else 1
        title = f"'{query}' (Page {page}/{total_pages}, {response.total} total)"
        
        table = Table(title=title)
        table.add_column("Path", style="cyan", no_wrap=False)
        table.add_column("Score", justify="right", style="magenta")

        for r in response.results:
            table.add_row(r.path, f"{r.score:.3f}")

        console.print(table)
        
        # Show navigation hints
        if page < total_pages:
            console.print(f"\n[dim]Next page: maven search \"{query}\" --page {page + 1}[/dim]")
        if page > 1:
            console.print(f"[dim]Previous page: maven search \"{query}\" --page {page - 1}[/dim]")