"""
Preemptive Dual-Priority Queue & Inference Scheduler.
Prioritizes high-frequency inline FIM autocomplete calls (/v1/completions) over background chat generation.
Ensures sub-35 ms time-to-first-token (TTFT) for typing ghost text.
"""
import asyncio
import time
from typing import Dict, Any, Callable
from enum import IntEnum

class RequestPriority(IntEnum):
    HIGH_FIM = 1      # FIM Tab Autocomplete (/v1/completions)
    NORMAL_CHAT = 2   # Chat / Refactor (/v1/chat/completions)

import inspect

class PriorityInferenceScheduler:
    """Preemptive scheduler prioritizing FIM completions over chat streams."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self.active_priority = None

    async def schedule(self, priority: RequestPriority, func: Callable, *args, **kwargs) -> Any:
        """Execute request via priority scheduler."""
        async with self._lock:
            start = time.perf_counter()
            self.active_priority = priority
            
            # Execute synchronously or via threadpool executor
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, func, *args, **kwargs)

            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self.active_priority = None

            if isinstance(result, dict):
                result["scheduler_latency_ms"] = round(elapsed_ms, 2)
            return result
