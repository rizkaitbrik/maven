"""Index management commands."""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from retrieval.services.config_manager import ConfigManager
from retrieval.services.index_manager import IndexManager
from retrieval.services.background_indexer import BackgroundIndexer

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
    
    # Initialize index manager
    index_manager = IndexManager(config.index, config.text_extensions)
    
    # Handle clear command
    if clear:
        if typer.confirm("Are you sure you want to clear the entire index?"):
            index_manager.clear()
            console.print("[green]✓[/green] Index cleared")
        return
    
    # Handle stats command
    if stats:
        index_stats = index_manager.get_stats()
        
        table = Table(title="Index Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Files Indexed", str(index_stats['file_count']))
        table.add_row("Total Size", f"{index_stats['total_size_bytes'] / 1024 / 1024:.2f} MB")
        
        if index_stats['last_indexed_at']:
            from datetime import datetime
            last_indexed = datetime.fromtimestamp(index_stats['last_indexed_at'])
            table.add_row("Last Indexed", last_indexed.strftime('%Y-%m-%d %H:%M:%S'))
        else:
            table.add_row("Last Indexed", "Never")
        
        table.add_row("Database Path", index_stats['db_path'])
        table.add_row("Watcher Enabled", str(config.index.enable_watcher))
        
        console.print(table)
        return
    
    # Start indexing
    indexer = BackgroundIndexer(index_manager, config)
    
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
        console=console
    ) as progress:
        
        task = progress.add_task("Indexing files...", total=100)
        
        def progress_callback(current: int, total: int):
            if total > 0:
                percent = (current / total) * 100
                progress.update(task, completed=percent, description=f"Indexed {current}/{total} files")
        
        # Start indexing
        indexer.start_indexing(
            root=config.root,
            rebuild=rebuild,
            progress_callback=progress_callback
        )
        
        # Wait for completion
        while indexer.is_indexing():
            import time
            time.sleep(0.1)
    
    # Show final stats
    indexed, total = indexer.get_progress()
    console.print(f"\n[green]✓[/green] Indexing complete: {indexed} files indexed")
    
    if config.index.enable_watcher:
        if indexer.get_watcher_status():
            console.print("[green]✓[/green] File system watcher started")
        else:
            console.print("[yellow]⚠[/yellow] File system watcher not started")

