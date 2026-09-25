"""
Ring-Buffer Logging Handler for Kingdom AI Server V2.
Captures log lines from Uvicorn, FastAPI, and Kingdom submodules into a thread-safe
in-memory ring buffer for display in the K-Top (htop-style) dashboard log pane.
"""
import logging
from collections import deque
from typing import List

class RingBufferLogHandler(logging.Handler):
    """Logging handler that appends formatted log records to a thread-safe sliding deque."""

    def __init__(self, capacity: int = 150):
        super().__init__()
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
        self.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.buffer.append(msg)
        except Exception:
            self.handleError(record)

    def get_recent_logs(self, limit: int = 8) -> List[str]:
        """Return the newest N log lines."""
        if not self.buffer:
            return ["[dim]No server events logged yet...[/dim]"]
        items = list(self.buffer)
        return items[-limit:]

    def clear(self) -> None:
        """Clear log buffer."""
        self.buffer.clear()

# Global singleton log buffer
log_buffer = RingBufferLogHandler()

def attach_log_interceptor(level: int = logging.INFO) -> RingBufferLogHandler:
    """Attaches the ring buffer handler to root and uvicorn loggers."""
    log_buffer.setLevel(level)
    
    # Intercept kingdom, uvicorn, and fastapi loggers
    for logger_name in ("", "uvicorn", "uvicorn.access", "uvicorn.error", "kingdom", "fastapi"):
        l = logging.getLogger(logger_name)
        # Avoid duplicate handlers
        if log_buffer not in l.handlers:
            l.addHandler(log_buffer)
            l.setLevel(level)

    return log_buffer
