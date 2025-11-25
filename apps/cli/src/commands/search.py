import json as json_lib
from pathlib import Path

import typer
from core.actions import SearchActions
from core.actions.search_actions import SearchType
from retrieval.services.config_manager import ConfigManager
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def search(
    query: str = typer.Argument(..., help="Search query or pattern"),
    root: str = typer.Option(None, help="Search root directory (overrides config)"),
    limit: int = typer.Option(10, help="Max results per page"),
    page: int = typer.Option(1, help="Page number"),
    json: bool = typer.Option(False, help="Output as JSON"),
    content: bool = typer.Option(
        False, "--content", "-c", help="Search inside file contents"
    ),
    hybrid: bool = typer.Option(
        False, "--hybrid", "-h", help="Use hybrid search (Spotlight + indexed content)"
    ),
):
    """Search files using platform-native indexing, content search, or hybrid mode."""

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
    search_root = Path(root) if root else config.root

    # Initialize search actions
    actions = SearchActions(config=config, root=search_root)

    # Determine search type
    if hybrid:
        search_type = SearchType.HYBRID
        search_label = "Hybrid Search"
    elif content:
        search_type = SearchType.CONTENT
        search_label = "Content Search"
    else:
        search_type = SearchType.FILENAME
        search_label = "File Search"

    # For hybrid search, check if index needs building
    if hybrid and config.index.auto_index_on_search:
        from core.actions import IndexActions

        index_actions = IndexActions(config=config)
        stats = index_actions.get_stats()

        if stats.file_count == 0:
            console.print(
                "[yellow]Index is empty, starting background indexing...[/yellow]"
            )

    # Execute search
    response = actions.search(
        query=query,
        search_type=search_type,
        page=page,
        size=limit,
        auto_index=hybrid,
    )

    if json:
        results_data = []
        for r in response.results:
            result_dict = {"path": r.path, "score": r.score}
            if r.snippet:
                result_dict["snippet"] = r.snippet
            if r.line_number:
                result_dict["line_number"] = r.line_number
            if r.match_type:
                result_dict["match_type"] = r.match_type
            results_data.append(result_dict)

        print(
            json_lib.dumps(
                {
                    "query": response.query,
                    "page": response.page,
                    "size": response.size,
                    "total": response.total,
                    "search_type": search_type.value,
                    "results": results_data,
                },
                indent=2,
            )
        )
    else:
        # Show pagination info
        total_pages = (response.total + limit - 1) // limit if limit > 0 else 1
        title = (
            f"{search_label}: '{query}' "
            f"(Page {page}/{total_pages}, {response.total} total)"
        )

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
                    console.print(Panel(r.snippet, border_style="dim", padding=(0, 1)))
        else:
            # For filename search, show table
            table = Table(title=title)
            table.add_column("Path", style="cyan", no_wrap=False)
            table.add_column("Score", justify="right", style="magenta")

            for r in response.results:
                table.add_row(r.path, f"{r.score:.3f}")

            console.print(table)

        # Show navigation hints
        mode_flag = " --hybrid" if hybrid else (" --content" if content else "")
        if page < total_pages:
            next_hint = f'maven search "{query}"{mode_flag} --page {page + 1}'
            console.print(f"\n[dim]Next page: {next_hint}[/dim]")
        if page > 1:
            prev_hint = f'maven search "{query}"{mode_flag} --page {page - 1}'
            console.print(f"[dim]Previous page: {prev_hint}[/dim]")
