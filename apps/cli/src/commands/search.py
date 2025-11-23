import asyncio
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel
from retrieval.adapters.spotlight import SpotlightAdapter
from retrieval.adapters.content_search import ContentSearchAdapter
from retrieval.models.search import SearchRequest, MatchType
from retrieval.services.config_manager import ConfigManager

console = Console()

def search(
    query: str = typer.Argument(..., help="Search query or pattern"),
    root: str = typer.Option(None, help="Search root directory (overrides config)"),
    limit: int = typer.Option(10, help="Max results per page"),
    page: int = typer.Option(1, help="Page number"),
    json: bool = typer.Option(False, help="Output as JSON"),
    content: bool = typer.Option(False, "--content", "-c", help="Search inside file contents")
):
    """Search files using platform-native indexing or content-based search."""
    
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
    
    # Choose adapter based on search type
    if content:
        adapter = ContentSearchAdapter(config.root, config=config)
        search_type = "content"
    else:
        adapter = SpotlightAdapter(config.root, config=config)
        search_type = "filename"
    
    request = SearchRequest(query=query, page=page, size=limit, config=config)

    response = asyncio.run(adapter.search(request))

    if json:
        import json as json_lib
        results_data = []
        for r in response.results:
            result_dict = {"path": r.path, "score": r.score}
            if r.snippet:
                result_dict["snippet"] = r.snippet
            if r.line_number:
                result_dict["line_number"] = r.line_number
            if r.match_type:
                result_dict["match_type"] = r.match_type.value
            results_data.append(result_dict)
        
        print(json_lib.dumps({
            "query": response.query,
            "page": response.page,
            "size": response.size,
            "total": response.total,
            "search_type": search_type,
            "results": results_data
        }, indent=2))
    else:
        # Show pagination info
        total_pages = (response.total + limit - 1) // limit if limit > 0 else 1
        search_label = "Content Search" if content else "File Search"
        title = f"{search_label}: '{query}' (Page {page}/{total_pages}, {response.total} total)"
        
        if content:
            # For content search, show snippets
            console.print(f"\n[bold]{title}[/bold]\n")
            
            for i, r in enumerate(response.results, start=1):
                # Header with file path and line number
                header = f"[cyan]{r.path}[/cyan]"
                if r.line_number:
                    header += f" [dim](Line {r.line_number})[/dim]"
                
                console.print(f"\n{i}. {header}")
                
                # Display snippet if available
                if r.snippet:
                    # Create a panel for the snippet
                    console.print(Panel(
                        r.snippet,
                        border_style="dim",
                        padding=(0, 1)
                    ))
        else:
            # For filename search, show table
            table = Table(title=title)
            table.add_column("Path", style="cyan", no_wrap=False)
            table.add_column("Score", justify="right", style="magenta")

            for r in response.results:
                table.add_row(r.path, f"{r.score:.3f}")

            console.print(table)
        
        # Show navigation hints
        content_flag = " --content" if content else ""
        if page < total_pages:
            console.print(f"\n[dim]Next page: maven search \"{query}\"{content_flag} --page {page + 1}[/dim]")
        if page > 1:
            console.print(f"[dim]Previous page: maven search \"{query}\"{content_flag} --page {page - 1}[/dim]")