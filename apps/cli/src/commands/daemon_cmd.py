"""Daemon management commands."""

import subprocess
from pathlib import Path

import typer
from core.actions import DaemonActions
from retrieval.services.config_manager import ConfigManager
from rich.console import Console
from rich.table import Table

console = Console()


def _get_daemon_actions() -> DaemonActions:
    """Get configured DaemonActions instance."""
    try:
        config = ConfigManager().config
        return DaemonActions(
            grpc_host=config.daemon.grpc_host,
            grpc_port=config.daemon.grpc_port,
            state_dir=Path(config.daemon.state_dir).expanduser(),
        )
    except Exception:
        # Fallback to defaults if config can't be loaded
        return DaemonActions()


def start(
    detach: bool = typer.Option(True, help="Run as background process"),
    use_launchctl: bool = typer.Option(
        True, "--launchctl/--no-launchctl", help="Use launchctl on macOS"
    ),
):
    """Start the Maven daemon."""
    console.print("[yellow]Starting Maven daemon...[/yellow]")

    actions = _get_daemon_actions()
    result = actions.start(detach=detach, use_launchctl=use_launchctl)

    if result.success:
        console.print(f"[green]✓[/green] {result.message}")
        if result.data and result.data.get("pid"):
            console.print(f"[dim]PID: {result.data['pid']}[/dim]")
    else:
        console.print(f"[red]✗[/red] {result.message}")


def stop(
    use_launchctl: bool = typer.Option(
        True, "--launchctl/--no-launchctl", help="Use launchctl on macOS"
    ),
):
    """Stop the Maven daemon."""
    console.print("[yellow]Stopping Maven daemon...[/yellow]")

    actions = _get_daemon_actions()
    result = actions.stop(use_launchctl=use_launchctl)

    if result.success:
        console.print(f"[green]✓[/green] {result.message}")
    else:
        console.print(f"[red]✗[/red] {result.message}")


def status():
    """Check daemon status."""
    actions = _get_daemon_actions()
    daemon_status = actions.status()

    if not daemon_status.running:
        console.print("[red]✗[/red] Daemon is not running")
        return

    table = Table(title="Maven Daemon Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Running", "✓ Yes" if daemon_status.running else "✗ No")
    table.add_row("PID", str(daemon_status.pid) if daemon_status.pid else "N/A")
    table.add_row("Uptime", daemon_status.uptime or "N/A")
    table.add_row(
        "Indexing", "✓ Active" if daemon_status.indexing else "✗ Idle"
    )
    table.add_row(
        "Watcher", "✓ Active" if daemon_status.watcher_active else "✗ Inactive"
    )
    table.add_row("Files Indexed", str(daemon_status.files_indexed))

    console.print(table)


def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "-n", help="Number of lines to show"),
):
    """View daemon logs."""
    actions = _get_daemon_actions()
    log_file = actions.get_log_path()

    if not log_file.exists():
        console.print(f"[red]✗[/red] Log file not found: {log_file}")
        return

    try:
        if follow:
            # Use tail -f
            subprocess.run(["tail", "-f", str(log_file)])
        else:
            # Show last N lines
            subprocess.run(["tail", "-n", str(lines), str(log_file)])
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to read logs: {e}")


def restart(
    use_launchctl: bool = typer.Option(
        True, "--launchctl/--no-launchctl", help="Use launchctl on macOS"
    ),
):
    """Restart the Maven daemon."""
    console.print("[yellow]Restarting Maven daemon...[/yellow]")

    actions = _get_daemon_actions()
    result = actions.restart(use_launchctl=use_launchctl)

    if result.success:
        console.print(f"[green]✓[/green] {result.message}")
    else:
        console.print(f"[red]✗[/red] {result.message}")

