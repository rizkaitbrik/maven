"""Daemon management commands."""

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def start(
    detach: bool = typer.Option(True, help="Run as background process")
):
    """Start the Maven daemon."""
    console.print("[yellow]Starting Maven daemon...[/yellow]")
    
    # Check if already running
    from daemon.state import DaemonStateManager
    state_mgr = DaemonStateManager()
    
    if state_mgr.is_running():
        console.print(f"[red]✗[/red] Daemon already running (PID: {state_mgr.get_pid()})")
        return
    
    # Start daemon
    if detach:
        # Start as background process
        subprocess.Popen(
            [sys.executable, "-m", "daemon.main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        console.print("[green]✓[/green] Daemon started in background")
    else:
        # Start in foreground
        subprocess.run([sys.executable, "-m", "daemon.main"])


def stop():
    """Stop the Maven daemon."""
    console.print("[yellow]Stopping Maven daemon...[/yellow]")
    
    import grpc
    from core import maven_pb2, maven_pb2_grpc
    from daemon.state import DaemonStateManager
    from retrieval.services.config_manager import ConfigManager
    
    state_mgr = DaemonStateManager()
    
    if not state_mgr.is_running():
        console.print("[red]✗[/red] Daemon is not running")
        return
    
    # Try to shutdown gracefully via gRPC
    try:
        config = ConfigManager().config
        channel = grpc.insecure_channel(f'{config.daemon.grpc_host}:{config.daemon.grpc_port}')
        stub = maven_pb2_grpc.DaemonServiceStub(channel)
        
        response = stub.Shutdown(maven_pb2.ShutdownRequest())
        
        if response.shutdown:
            console.print("[green]✓[/green] Daemon stopped")
        else:
            console.print(f"[yellow]⚠[/yellow] {response.message}")
    
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to stop daemon: {e}")


def status():
    """Check daemon status."""
    import grpc
    from core import maven_pb2, maven_pb2_grpc
    from daemon.state import DaemonStateManager
    from retrieval.services.config_manager import ConfigManager
    
    state_mgr = DaemonStateManager()
    
    if not state_mgr.is_running():
        console.print("[red]✗[/red] Daemon is not running")
        return
    
    # Get status via gRPC
    try:
        config = ConfigManager().config
        channel = grpc.insecure_channel(f'{config.daemon.grpc_host}:{config.daemon.grpc_port}')
        stub = maven_pb2_grpc.DaemonServiceStub(channel)
        
        response = stub.GetStatus(maven_pb2.StatusRequest())
        
        table = Table(title="Maven Daemon Status")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Running", "✓ Yes" if response.running else "✗ No")
        table.add_row("PID", str(response.pid))
        table.add_row("Uptime", response.uptime)
        table.add_row("Indexing", "✓ Active" if response.indexing else "✗ Idle")
        table.add_row("Watcher", "✓ Active" if response.watcher_active else "✗ Inactive")
        table.add_row("Files Indexed", str(response.files_indexed))
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to get status: {e}")


def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "-n", help="Number of lines to show")
):
    """View daemon logs."""
    from retrieval.services.config_manager import ConfigManager
    
    try:
        config = ConfigManager().config
        log_dir = Path(config.logging.log_dir).expanduser()
        log_file = log_dir / "maven.daemon.log"
        
        if not log_file.exists():
            console.print(f"[red]✗[/red] Log file not found: {log_file}")
            return
        
        if follow:
            # Use tail -f
            subprocess.run(["tail", "-f", str(log_file)])
        else:
            # Show last N lines
            subprocess.run(["tail", "-n", str(lines), str(log_file)])
    
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to read logs: {e}")


def restart():
    """Restart the Maven daemon."""
    stop()
    import time
    time.sleep(1)
    start()

