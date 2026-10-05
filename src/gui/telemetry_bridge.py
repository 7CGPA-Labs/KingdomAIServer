"""
Telemetry Bridge for Kingdom AI Studio V3.
Periodically samples CPU, RAM, GPU, VRAM, and response cache telemetry,
pushing real-time updates directly into Slint UI properties via native event loop invocations.
"""
import time
import logging
import threading
from typing import Optional, Any
import slint

from src.utils.telemetry import HardwareTelemetry
from src.gui.dispatcher import dispatch_ui

logger = logging.getLogger("kingdom.gui.telemetry")


class TelemetryBridge:
    """Bridges background hardware and cache metrics to the Slint MainWindow."""

    def __init__(self, ui_handle: Any, cache_db: Optional[Any] = None, poll_interval_sec: float = 0.5, orchestrator: Optional[Any] = None):
        self.ui = ui_handle
        self.cache_db = cache_db
        self.orchestrator = orchestrator
        self.poll_interval = poll_interval_sec
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = time.time()

    def start(self) -> None:
        """Start the background telemetry sampling thread."""
        if self._running:
            return
        self._running = True
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="KingdomTelemetryBridge")
        self._thread.start()
        logger.info("TelemetryBridge thread started (interval: %ss)", self.poll_interval)

    def stop(self) -> None:
        """Stop the background telemetry polling thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        logger.info("TelemetryBridge thread stopped")

    def _format_uptime(self) -> str:
        elapsed = int(time.time() - self._start_time)
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"

    def update_once(self) -> None:
        """Execute a single telemetry snapshot and update Slint UI properties."""
        try:
            snap = HardwareTelemetry.snapshot()
            uptime = self._format_uptime()

            cache_entries = 0
            cache_hits = 0
            cache_hit_ratio = 0.0

            if self.cache_db:
                try:
                    c_stats = self.cache_db.get_stats()
                    cache_entries = c_stats.get("total_cached_entries", 0)
                    cache_hits = c_stats.get("total_cache_hits", 0)
                    cache_hit_ratio = float(c_stats.get("hit_ratio_pct", 0.0))
                except Exception:
                    pass

            cpu_val = float(snap.get("cpu_percent", 0.0))
            ram_used = float(snap.get("ram_used_gb", 0.0))
            ram_total = float(snap.get("ram_total_gb", 16.0))
            vram_used = float(snap.get("vram_used_gb", 0.0))
            gpu_name = str(snap.get("gpu_engine", "GPU Accelerated"))
            vram_status_str = f"{vram_used:.2f} / 6.00 GB"

            def _apply():
                try:
                    self.ui.cpu_pct = cpu_val
                    self.ui.ram_used_gb = ram_used
                    self.ui.ram_total_gb = ram_total
                    self.ui.vram_used_gb = vram_used
                    self.ui.vram_ceiling_gb = 6.0
                    self.ui.vram_status = vram_status_str
                    self.ui.uptime_str = uptime
                    if cache_entries > 0:
                        self.ui.cache_entries = cache_entries
                        self.ui.cache_hits = cache_hits
                        self.ui.cache_hit_ratio = cache_hit_ratio
                    # Only update silicon provider if non-empty
                    if gpu_name:
                        self.ui.silicon_provider = f"Vulkan / {gpu_name}"
                    if self.orchestrator and hasattr(self.ui, "boss_status"):
                        is_loaded = getattr(self.orchestrator, "is_loaded", False)
                        if is_loaded:
                            self.ui.boss_status = "ACTIVE"
                        elif getattr(self.ui, "boss_status", "") not in ("ACTIVE", "LOADING"):
                            self.ui.boss_status = "STANDBY"
                except Exception as e:
                    logger.debug("Failed applying telemetry to UI: %s", e)

            dispatch_ui(_apply)
        except Exception as e:
            logger.debug("Telemetry snapshot failed: %s", e)

    def _poll_loop(self) -> None:
        """Background thread loop polling hardware telemetry."""
        while self._running:
            self.update_once()
            time.sleep(self.poll_interval)
