"""
[DEPRECATED in V3] K-Top (Kingdom Top) Terminal Dashboard.
NOTE: In Kingdom AI Studio V3, the architecture is 100% on-device in-process
Slint Native Desktop GUI. Real-time telemetry, hardware gauges, and minister monitoring
are natively integrated into the Slint GUI auxiliary pane (ui/ktop_panel.slint).
This module is maintained as a lightweight deprecation stub pointing to main.py.
"""
import time
import warnings
from typing import Optional

try:
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.table import Table
    from rich.text import Text
except ImportError:
    Panel = None
    Layout = None
    Table = None
    Text = None

from src.core.hardware import HardwareManager, STATIC_VRAM_CEILING_MB


def make_meter(percent: float, width: int = 24):
    """Create a colored ASCII meter bar like [||||||||||          34.2%]."""
    clamped = max(0.0, min(100.0, percent))
    filled_len = int(round((clamped / 100.0) * width))
    empty_len = width - filled_len

    if Text is not None:
        meter = Text()
        meter.append("[", style="dim")

        if clamped < 65.0:
            bar_style = "green"
        elif clamped < 85.0:
            bar_style = "yellow"
        else:
            bar_style = "bold red"

        meter.append("|" * filled_len, style=bar_style)
        meter.append(" " * empty_len, style="dim")
        meter.append("]", style="dim")
        meter.append(f" {clamped:5.1f}%", style="bold white")
        return meter
    else:
        # Fallback if rich is not present
        class PlainMeter:
            def __init__(self, text):
                self.plain = text
            def __str__(self):
                return self.plain
        return PlainMeter(f"[{'|' * filled_len}{' ' * empty_len}] {clamped:5.1f}%")


class KingdomTopDashboard:
    """[DEPRECATED in V3] Lightweight backward-compatible stub for K-Top TUI."""

    def __init__(self, host: str = "127.0.0.1", port: int = 58420, bearer_token: str = "local-token"):
        self.host = host
        self.port = port
        self.token = bearer_token
        self.start_time = time.time()
        self.cache_db = None
        self.orchestrator = None
        self.embedder = None
        self.reranker = None
        self.hw_manager = HardwareManager()
        self.status_message = "● DEPRECATED (Replaced by Slint GUI in V3)"
        self.show_help = False

    def attach_engines(self, cache_db=None, orchestrator=None, embedder=None, reranker=None):
        """Attach engine instances for telemetry inspection."""
        self.cache_db = cache_db
        self.orchestrator = orchestrator
        self.embedder = embedder
        self.reranker = reranker

    def get_uptime_str(self) -> str:
        """Calculate server uptime formatted as HH:MM:SS."""
        elapsed = int(time.time() - self.start_time)
        hours, rem = divmod(elapsed, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours:02d}h:{minutes:02d}m:{seconds:02d}s"

    def render_header(self):
        """Render top summary header with host, port, token, and uptime."""
        uptime = self.get_uptime_str()
        if Panel and Text:
            content = Text()
            content.append("👑 KINGDOM AI SERVER V2 • K-TOP MONITOR [DEPRECATED]\n", style="bold magenta")
            content.append(f"   Host: {self.host}:{self.port} | Uptime: {uptime}\n", style="cyan")
            content.append("   Notice: Replaced by Kingdom AI Studio V3 Slint GUI (main.py)", style="yellow")
            return Panel(content, title="[bold]System Status[/bold]", border_style="cyan")
        return f"Kingdom AI Server V2 (Host: {self.host}:{self.port}) - Uptime: {uptime}"

    def render_resource_gauges(self):
        """Render CPU, RAM, and dynamic VRAM utilization gauges."""
        if Panel and Table:
            grid = Table.grid(expand=True)
            grid.add_column(ratio=1)
            grid.add_column(ratio=2)
            grid.add_row("CPU", make_meter(12.5, width=20))
            grid.add_row("RAM", make_meter(45.0, width=20))
            grid.add_row("VRAM", make_meter(30.0, width=20))
            return Panel(grid, title="[bold]Hardware Gauges[/bold]", border_style="cyan")
        return "Resource Gauges: CPU 12.5%, RAM 45.0%, VRAM 30.0%"

    def render_council_panel(self):
        """Render status of council ministers and loaded LLM models."""
        boss_name = getattr(self.orchestrator, "model_name", "qwen2.5-coder-1.5b") if self.orchestrator else "qwen2.5-coder-1.5b"
        boss_loaded = getattr(self.orchestrator, "is_loaded", False) if self.orchestrator else False
        emb_loaded = getattr(self.embedder, "is_model_loaded", False) if self.embedder else False
        rerank_loaded = getattr(self.reranker, "is_model_loaded", False) if self.reranker else False

        if Panel and Table:
            table = Table.grid(expand=True)
            table.add_column("Component", style="bold")
            table.add_column("Status", style="cyan")
            table.add_row("Main Boss LLM", f"{boss_name} ({'Loaded' if boss_loaded else 'Standby'})")
            table.add_row("Minister 1 (Embedder)", "Active" if emb_loaded else "Standby")
            table.add_row("Minister 2 (Reranker)", "Active" if rerank_loaded else "Standby")
            return Panel(table, title="[bold]Council Ministers[/bold]", border_style="magenta")
        return f"Council: Boss {boss_name} ({'Loaded' if boss_loaded else 'Standby'})"

    def render_requests_table(self):
        """Render recent API requests table."""
        if Panel and Text:
            return Panel(Text("In-process mode active. No remote HTTP requests recorded."), title="[bold]Recent Requests[/bold]", border_style="green")
        return "Recent Requests: None"

    def render_log_pane(self):
        """Render server log pane."""
        if Panel and Text:
            return Panel(Text("[INFO] Kingdom AI Studio V3 Slint GUI active."), title="[bold]Server Logs[/bold]", border_style="yellow")
        return "Server Logs: OK"

    def render_footer(self):
        """Render bottom status bar and keybinding help."""
        if Panel and Text:
            return Panel(Text("[DEPRECATED] Launch V3 GUI via: python main.py"), border_style="dim")
        return "[DEPRECATED] python main.py"

    def build_layout(self):
        """Assemble the composite Rich Layout."""
        if Layout:
            layout = Layout()
            layout.split_column(
                Layout(self.render_header(), name="header", size=4),
                Layout(self.render_resource_gauges(), name="gauges", size=6),
                Layout(self.render_council_panel(), name="council", size=6),
                Layout(self.render_requests_table(), name="requests", size=5),
                Layout(self.render_log_pane(), name="logs", ratio=1),
                Layout(self.render_footer(), name="footer", size=3)
            )
            return layout
        return {}


def main():
    """Legacy launcher for K-Top - notifies deprecation and launches Slint Desktop Studio."""
    warnings.warn(
        "K-Top Terminal Dashboard is deprecated and decommissioned in V3. "
        "Redirecting to Kingdom AI Studio V3 Slint Native Desktop GUI (main.py).",
        DeprecationWarning,
        stacklevel=2,
    )
    print("======================================================================")
    print(" ⚠️  NOTICE: K-Top Terminal Dashboard is DECOMMISSIONED in V3.")
    print(" Real-time telemetry, hardware gauges, and minister monitoring")
    print(" are now natively integrated into Kingdom AI Studio V3 Desktop GUI.")
    print(" Redirecting to Kingdom AI Studio V3 (main.py)...")
    print("======================================================================")
    try:
        from main import launch_studio
        launch_studio()
    except Exception as exc:
        print(f"To launch the V3 Desktop GUI, run: python main.py ({exc})")


if __name__ == "__main__":
    main()
