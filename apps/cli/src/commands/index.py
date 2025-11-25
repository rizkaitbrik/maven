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
)
from rich.table import Table

console = Console()


def index(
    root: str = typer.Option(None, help="Root directory to index (overrides config)"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Rebuild the entire index"),
    stats: bool = typer.Option(False, "--stats", help="Show index statistics"),
    clear: bool = typer.Option(False, "--clear", help="Clear the index"),
):
    """Manage the search index."""

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
        if typer.confirm("Are you sure you want to clear the entire index?"):
            result = actions.clear_index()
            console.print(f"[green]✓[/green] {result.message}")
        return

    # Handle stats command
    if stats:
        index_stats = actions.get_stats()

        table = Table(title="Index Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Files Indexed", str(index_stats.file_count))
        table.add_row(
            "Total Size", f"{index_stats.total_size_bytes / 1024 / 1024:.2f} MB"
        )

        if index_stats.last_indexed_at:
            from datetime import datetime

            last_indexed = datetime.fromtimestamp(index_stats.last_indexed_at)
            table.add_row("Last Indexed", last_indexed.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            table.add_row("Last Indexed", "Never")

        table.add_row("Database Path", index_stats.db_path)
        table.add_row("Watcher Enabled", str(index_stats.watcher_enabled))

        console.print(table)
        return

    # Start indexing
    if rebuild:
        console.print("[yellow]Rebuilding entire index...[/yellow]")
    else:
        console.print("[yellow]Starting incremental indexing...[/yellow]")

    # Track progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing files...", total=100)

        def progress_callback(current: int, total: int):
            if total > 0:
                percent = (current / total) * 100
                desc = f"Indexed {current}/{total} files"
                progress.update(task, completed=percent, description=desc)

        # Start indexing
        actions.start_indexing(
            root=config.root,
            rebuild=rebuild,
            progress_callback=progress_callback,
        )

        # Wait for completion
        indexed, total = actions.wait_for_completion()

    # Show final stats
    console.print(f"\n[green]✓[/green] Indexing complete: {indexed} files indexed")

    watcher_status = actions.get_watcher_status()
    if watcher_status:
        console.print("[green]✓[/green] File system watcher started")
    else:
        console.print("[yellow]⚠[/yellow] File system watcher not started")

