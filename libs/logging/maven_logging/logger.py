"""Maven centralized logger."""

import logging
from pathlib import Path
from typing import Any

from maven_logging.formatters import LogfmtFormatter
from maven_logging.handlers import (
    create_console_handler,
    create_file_handler,
    create_syslog_handler,
)


class MavenLogger:
    """Centralized logger for Maven components."""
    
    def __init__(
        self,
        name: str,
        log_dir: Path | None = None,
        level: str = "INFO",
        max_file_size: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        enable_syslog: bool = True,
        enable_console: bool = True
    ):
        """Initialize Maven logger.
        
        Args:
            name: Logger name (will be prefixed with 'maven.')
            log_dir: Directory for log files
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            max_file_size: Maximum log file size before rotation
            backup_count: Number of backup files to keep
            enable_syslog: Whether to enable syslog handler
            enable_console: Whether to enable console handler
        """
        self.name = f'maven.{name}'
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(getattr(logging, level.upper()))
        self.logger.propagate = False  # Don't propagate to root logger
        
        self.log_dir = log_dir or Path.home() / '.maven' / 'logs'
        self.formatter = LogfmtFormatter()
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Setup handlers
        self._setup_file_handler(max_file_size, backup_count)
        
        if enable_console:
            self._setup_console_handler()
        
        if enable_syslog:
            self._setup_syslog_handler()
    
    def _setup_file_handler(self, max_bytes: int, backup_count: int):
        """Setup rotating file handler."""
        log_file = self.log_dir / f'{self.name}.log'
        handler = create_file_handler(
            log_file,
            max_bytes=max_bytes,
            backup_count=backup_count,
            formatter=self.formatter
        )
        self.logger.addHandler(handler)
    
    def _setup_console_handler(self):
        """Setup console handler."""
        handler = create_console_handler(formatter=self.formatter)
        self.logger.addHandler(handler)
    
    def _setup_syslog_handler(self):
        """Setup syslog handler if available."""
        handler = create_syslog_handler(formatter=self.formatter)
        if handler:
            self.logger.addHandler(handler)
    
    def _log(self, level: int, msg: str, **kwargs):
        """Log a message with extra context.
        
        Args:
            level: Log level
            msg: Log message
            **kwargs: Extra context to include in log
        """
        # Add kwargs as extra fields to the log record
        extra_dict = {k: v for k, v in kwargs.items()}
        self.logger.log(level, msg, extra=extra_dict, stacklevel=2)
    
    def debug(self, msg: str, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, msg, **kwargs)
    
    def info(self, msg: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, msg, **kwargs)
    
    def warning(self, msg: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, msg, **kwargs)
    
    def error(self, msg: str, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, msg, **kwargs)
    
    def critical(self, msg: str, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, msg, **kwargs)
    
    def exception(self, msg: str, **kwargs):
        """Log exception with traceback."""
        self.logger.exception(msg, extra=kwargs, stacklevel=2)


# Global logger cache
_loggers: dict[str, MavenLogger] = {}


def get_logger(
    name: str,
    log_dir: Path | None = None,
    level: str = "INFO",
    **kwargs
) -> MavenLogger:
    """Get or create a Maven logger.
    
    Args:
        name: Logger name
        log_dir: Log directory
        level: Log level
        **kwargs: Additional logger arguments
        
    Returns:
        Maven logger instance
    """
    if name not in _loggers:
        _loggers[name] = MavenLogger(
            name,
            log_dir=log_dir,
            level=level,
            **kwargs
        )
    return _loggers[name]


def configure_from_config(config: Any):
    """Configure logging from Maven config object.
    
    Args:
        config: Config object with logging settings
    """
    if not hasattr(config, 'logging'):
        return
    
    log_config = config.logging
    
    # Set defaults for get_logger
    global _default_log_dir, _default_level
    _default_log_dir = Path(log_config.log_dir).expanduser()
    _default_level = log_config.level


# Default configuration
_default_log_dir = Path.home() / '.maven' / 'logs'
_default_level = "INFO"

