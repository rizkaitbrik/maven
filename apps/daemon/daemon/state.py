"""Daemon state management with PID file and SQLite."""

import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path


class DaemonStateManager:
    """Manages daemon state using PID file and SQLite database."""
    
    def __init__(self, state_dir: Path | None = None):
        """Initialize state manager.
        
        Args:
            state_dir: Directory for state files (default: ~/.maven)
        """
        self.state_dir = state_dir or Path.home() / '.maven'
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        self.pid_file = self.state_dir / 'daemon.pid'
        self.db_path = self.state_dir / 'daemon_state.db'
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize state database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daemon_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at REAL
                )
            """)
            conn.commit()
    
    def is_running(self) -> bool:
        """Check if daemon is running via PID file.
        
        Returns:
            True if daemon process is running
        """
        if not self.pid_file.exists():
            return False
        
        try:
            pid = int(self.pid_file.read_text().strip())
            
            # Check if process exists
            try:
                os.kill(pid, 0)  # Signal 0 just checks existence
                return True
            except OSError:
                # Process doesn't exist, clean up stale PID file
                self.pid_file.unlink(missing_ok=True)
                return False
        except (OSError, ValueError):
            return False
    
    def get_pid(self) -> int | None:
        """Get daemon PID from PID file.
        
        Returns:
            PID or None if not running
        """
        if not self.pid_file.exists():
            return None
        
        try:
            return int(self.pid_file.read_text().strip())
        except (OSError, ValueError):
            return None
    
    def write_pid(self, pid: int | None = None):
        """Write PID file.
        
        Args:
            pid: Process ID (defaults to current process)
        """
        pid = pid or os.getpid()
        self.pid_file.write_text(str(pid))
        
        # Also store in database
        self.set_state('pid', str(pid))
        self.set_state('started_at', str(time.time()))
    
    def remove_pid(self):
        """Remove PID file."""
        self.pid_file.unlink(missing_ok=True)
        self.set_state('stopped_at', str(time.time()))
    
    def get_state(self, key: str) -> str | None:
        """Get state value from database.
        
        Args:
            key: State key
            
        Returns:
            State value or None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value FROM daemon_state WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
    
    def set_state(self, key: str, value: str):
        """Set state value in database.
        
        Args:
            key: State key
            value: State value
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO daemon_state (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, time.time()))
            conn.commit()
    
    def get_status(self) -> dict:
        """Get comprehensive daemon status.
        
        Returns:
            Status dictionary
        """
        status = {
            'running': self.is_running(),
            'pid': self.get_pid(),
        }
        
        # Get uptime
        started_at_str = self.get_state('started_at')
        if started_at_str:
            try:
                started_at = float(started_at_str)
                uptime_seconds = time.time() - started_at
                status['uptime'] = self._format_uptime(uptime_seconds)
                status['started_at'] = datetime.fromtimestamp(started_at).isoformat()
            except ValueError:
                pass
        
        # Get other state
        status['indexing'] = self.get_state('indexing') == 'true'
        status['watcher_active'] = self.get_state('watcher_active') == 'true'
        status['files_indexed'] = int(self.get_state('files_indexed') or '0')
        
        return status
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime as human-readable string.
        
        Args:
            seconds: Uptime in seconds
            
        Returns:
            Formatted uptime (e.g., "2h 34m")
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return f"{int(seconds)}s"
    
    def set_indexing(self, indexing: bool):
        """Set indexing status.
        
        Args:
            indexing: Whether indexing is active
        """
        self.set_state('indexing', 'true' if indexing else 'false')
    
    def set_watcher_active(self, active: bool):
        """Set watcher status.
        
        Args:
            active: Whether watcher is active
        """
        self.set_state('watcher_active', 'true' if active else 'false')
    
    def set_files_indexed(self, count: int):
        """Set files indexed count.
        
        Args:
            count: Number of files indexed
        """
        self.set_state('files_indexed', str(count))

