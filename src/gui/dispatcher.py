"""
Thread-safe UI callback dispatcher for Slint desktop applications.
Handles seamless dispatching across different Slint versions, including Slint < 1.10
where invoke_from_event_loop is not available on Python bindings.
"""
import queue
import logging
import threading
from typing import Callable, Optional
import slint

logger = logging.getLogger("kingdom.gui.dispatcher")

_ui_queue: queue.Queue = queue.Queue()

def has_native_event_loop_invocation() -> bool:
    """Returns True if the runtime Slint build provides invoke_from_event_loop."""
    return bool(
        getattr(slint, "invoke_from_event_loop", None)
        or getattr(getattr(slint, "native", None), "invoke_from_event_loop", None)
    )

def dispatch_ui(callback: Callable[[], None]) -> None:
    """Dispatches a callback to the Slint UI thread safely across Slint versions."""
    if threading.current_thread() is threading.main_thread():
        try:
            callback()
        except Exception as e:
            logger.debug("Direct UI callback failed: %s", e)
        return

    invoke_fn = getattr(slint, "invoke_from_event_loop", None) or getattr(getattr(slint, "native", None), "invoke_from_event_loop", None)
    if invoke_fn:
        try:
            invoke_fn(callback)
            return
        except Exception:
            pass

    # In environments/versions lacking invoke_from_event_loop, enqueue for main thread execution
    _ui_queue.put(callback)

def process_pending_ui_callbacks() -> int:
    """Processes all pending UI callbacks on the current (main) thread.
    Returns the number of callbacks executed.
    """
    count = 0
    while not _ui_queue.empty():
        try:
            fn = _ui_queue.get_nowait()
            fn()
            count += 1
        except queue.Empty:
            break
        except Exception as e:
            logger.debug("Pending UI callback failed: %s", e)
    return count
