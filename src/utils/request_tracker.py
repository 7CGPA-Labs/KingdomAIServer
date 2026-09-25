"""
Thread-safe In-Memory Request, Inference & Log Telemetry Tracker for Kingdom AI Server V2.
Captures real-time metrics for K-Top (htop-style dashboard):
- Request ID, Timestamp, Method, Endpoint, Priority, HTTP Status, Latency (ms)
- Tokens generated and inference generation speed (tokens/sec)
- Intercepted Uvicorn and FastAPI application log event ring buffer
"""
import time
import logging
import threading
from collections import deque
from typing import List, Dict, Any, Optional

class RequestTracker:
    """Singleton tracker maintaining a fixed ring-buffer of recent and active inference requests."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RequestTracker, cls).__new__(cls)
                cls._instance._init_tracker()
            return cls._instance

    def _init_tracker(self):
        self._buffer_lock = threading.Lock()
        self._recent_requests = deque(maxlen=40)
        self._active_requests = {}
        self.total_requests = 0
        self.total_tokens_generated = 0
        self.last_inference_speed = 0.0

    def record_request_start(self, req_id: str, method: str, path: str, priority: str = "NORMAL") -> None:
        """Record the beginning of an incoming HTTP request."""
        with self._buffer_lock:
            self.total_requests += 1
            start_record = {
                "id": req_id,
                "timestamp": time.strftime("%H:%M:%S"),
                "start_time": time.perf_counter(),
                "method": method,
                "path": path,
                "priority": priority,
                "status": "RUNNING",
                "latency_ms": 0.0,
                "tokens": 0,
                "tokens_per_sec": 0.0,
            }
            self._active_requests[req_id] = start_record
            self._recent_requests.appendleft(start_record)

    def record_request_end(
        self,
        req_id: str,
        status_code: int = 200,
        tokens_generated: int = 0,
        tokens_per_sec: Optional[float] = None
    ) -> None:
        """Finalize request completion with status, latency, and throughput metrics."""
        with self._buffer_lock:
            record = self._active_requests.pop(req_id, None)
            if not record:
                # Find in recent requests if already present
                for r in self._recent_requests:
                    if r["id"] == req_id:
                        record = r
                        break

            if record:
                elapsed_ms = (time.perf_counter() - record.get("start_time", time.perf_counter())) * 1000.0
                record["status"] = str(status_code)
                record["latency_ms"] = round(elapsed_ms, 2)
                record["tokens"] = tokens_generated
                if tokens_per_sec is not None:
                    record["tokens_per_sec"] = round(tokens_per_sec, 1)
                    self.last_inference_speed = round(tokens_per_sec, 1)
                elif tokens_generated > 0 and elapsed_ms > 0:
                    speed = (tokens_generated / (elapsed_ms / 1000.0))
                    record["tokens_per_sec"] = round(speed, 1)
                    self.last_inference_speed = round(speed, 1)

                self.total_tokens_generated += tokens_generated

    def get_recent_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return snapshot of most recent requests (newest first)."""
        with self._buffer_lock:
            return list(self._recent_requests)[:limit]

    def get_active_count(self) -> int:
        """Return number of currently executing requests."""
        with self._buffer_lock:
            return len(self._active_requests)

    def get_stats(self) -> Dict[str, Any]:
        """Return high-level summary metrics."""
        with self._buffer_lock:
            return {
                "total_requests": self.total_requests,
                "active_requests": len(self._active_requests),
                "total_tokens_generated": self.total_tokens_generated,
                "last_tokens_per_sec": self.last_inference_speed,
            }

    def clear(self) -> None:
        """Reset the request tracker."""
        with self._buffer_lock:
            self._recent_requests.clear()
            self._active_requests.clear()
            self.total_requests = 0
            self.total_tokens_generated = 0
            self.last_inference_speed = 0.0

tracker = RequestTracker()


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
        if log_buffer not in l.handlers:
            l.addHandler(log_buffer)
            l.setLevel(level)

    return log_buffer
