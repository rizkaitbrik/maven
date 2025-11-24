"""Log handlers for Maven."""

import logging
import logging.handlers
import sys
from pathlib import Path


def create_file_handler(
    log_file: Path,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    formatter: logging.Formatter | None = None
) -> logging.Handler:
    """Create a rotating file handler.
    
    Args:
        log_file: Path to log file
        max_bytes: Maximum file size before rotation
        backup_count: Number of backup files to keep
        formatter: Log formatter to use
        
    Returns:
        Configured file handler
    """
    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    if formatter:
        handler.setFormatter(formatter)
    
    return handler


def create_console_handler(
    formatter: logging.Formatter | None = None,
    stream=None
) -> logging.Handler:
    """Create a console (stdout/stderr) handler.
    
    Args:
        formatter: Log formatter to use
        stream: Stream to write to (defaults to stderr)
        
    Returns:
        Configured console handler
    """
    handler = logging.StreamHandler(stream or sys.stderr)
    
    if formatter:
        handler.setFormatter(formatter)
    
    return handler


def create_syslog_handler(
    address: str | tuple = '/dev/log',
    facility: int = logging.handlers.SysLogHandler.LOG_USER,
    formatter: logging.Formatter | None = None
) -> logging.Handler | None:
    """Create a syslog handler.
    
    Args:
        address: Syslog address (path or (host, port) tuple)
        facility: Syslog facility
        formatter: Log formatter to use
        
    Returns:
        Configured syslog handler or None if syslog not available
    """
    try:
        # Try common syslog paths
        syslog_paths = ['/dev/log', '/var/run/syslog', ('localhost', 514)]
        
        if isinstance(address, str) and not Path(address).exists():
            # Try alternatives
            for path in syslog_paths:
                is_valid = (
                    (isinstance(path, str) and Path(path).exists())
                    or isinstance(path, tuple)
                )
                if is_valid:
                    address = path
                    break
        
        handler = logging.handlers.SysLogHandler(
            address=address,
            facility=facility
        )
        
        if formatter:
            handler.setFormatter(formatter)
        
        return handler
    except (OSError, FileNotFoundError):
        # Syslog not available
        return None

