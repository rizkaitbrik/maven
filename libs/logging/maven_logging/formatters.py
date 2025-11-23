"""Log formatters for Maven."""

import logging
from datetime import datetime


class LogfmtFormatter(logging.Formatter):
    """Logfmt formatter: level=INFO ts=2025-01-01T12:00:00 msg="message" key=value"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as logfmt key=value pairs.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log string
        """
        # Build key=value pairs
        parts = [
            f'level={record.levelname}',
            f'ts={datetime.fromtimestamp(record.created).isoformat()}',
            f'component={record.name}',
        ]
        
        # Add message (quoted if contains spaces)
        msg = record.getMessage()
        if ' ' in msg or '"' in msg:
            # Escape quotes and wrap in quotes
            msg = msg.replace('"', '\\"')
            parts.append(f'msg="{msg}"')
        else:
            parts.append(f'msg={msg}')
        
        # Add exception info if present
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            if exc_text:
                exc_text = exc_text.replace('\n', '\\n').replace('"', '\\"')
                parts.append(f'error="{exc_text}"')
        
        # Add extra context from record.__dict__
        # Skip standard logging attributes
        skip_keys = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'message', 'pathname', 'process', 'processName',
            'relativeCreated', 'thread', 'threadName', 'exc_info',
            'exc_text', 'stack_info', 'taskName'
        }
        
        for key, value in record.__dict__.items():
            if key not in skip_keys and not key.startswith('_'):
                # Format value
                if isinstance(value, str):
                    if ' ' in value or '"' in value:
                        value = value.replace('"', '\\"')
                        parts.append(f'{key}="{value}"')
                    else:
                        parts.append(f'{key}={value}')
                else:
                    parts.append(f'{key}={value}')
        
        return ' '.join(parts)

