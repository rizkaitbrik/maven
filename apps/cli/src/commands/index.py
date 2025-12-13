"""Index management commands."""

from pathlib import Path

import typer
from core.actions import IndexActions
from retrieval.services.config_manager import ConfigManager
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

console = Console()


def index(
    root: str = typer.Option(None, help="Root directory to index (overrides config)"),
    rebuild: bool = typer.Option(False, "--rebuild", "--force", help="Rebuild the entire index (ignore modification times)"),
    stats: bool = typer.Option(False, "--stats", help="Show index statistics"),
    clear: bool = typer.Option(False, "--clear", help="Clear the index"),
):
    """Manage the semantic search index."""

    # Load configuration
    try:
        config_manager = ConfigManager()
        config = config_manager.config
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return

    # Override root if specified
    if root:
        config.root = Path(root)

    # Initialize index actions with config
    actions = IndexActions(config=config)

    # Handle clear command
    if clear:
        if typer.confirm("Are you sure you want to clear the entire semantic index?"):
            result = actions.clear_index()
            console.print(f"[green]✓[/green] {result.message}")
        return

    # Handle stats command
    if stats:
        index_stats = actions.get_stats

        table = Table(title="Semantic Index Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Files/Chunks Indexed", str(index_stats.file_count))
        table.add_row("Database Path", index_stats.db_path)
        
        console.print(table)
        return

    # Start indexing
    if rebuild:
        console.print("[yellow]Rebuilding index (force update)...[/yellow]")
    else:
        console.print("[yellow]Synchronizing index (incremental update)...[/yellow]")

    # Track progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning files...", total=None)

        def progress_callback(current: int, total: int, message: str = ""):
            if total > 0:
                progress.update(task, total=total, completed=current, description=message)
            else:
                 progress.update(task, completed=current, description=message)

        # Start indexing (synchronous)
        result = actions.start_indexing(
            root=config.root,
            rebuild=rebuild,
            progress_callback=progress_callback,
        )

        if result.success:
            data = result.data or {}
            console.print("\n[green]✓[/green] Indexing complete!")
            console.print(f"Scanned files: {data.get('total_files', 0)}")
            console.print(f"Successfully indexed: {data.get('success_count', 0)}")
            console.print(f"Total chunks generated: {data.get('total_chunks', 0)}")
        else:
            console.print(f"\n[red]Indexing failed: {result.message}[/red]")

