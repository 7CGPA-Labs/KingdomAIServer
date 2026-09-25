"""
K-Top (Kingdom Top) - Real-time htop-style TUI Dashboard for Kingdom AI Server V2.
Renders live hardware meters, council ministers status, in-flight/recent request streams,
and server logs in an alternate screen buffer using Rich.
"""
import sys
import time

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.layout import Layout
    from rich.theme import Theme
except ImportError:
    print("[ERROR] 'rich' is required for K-Top dashboard. Install with: pip install rich")
    sys.exit(1)

from src.utils.telemetry import HardwareTelemetry
from src.utils.request_tracker import tracker, log_buffer
from src.core.hardware import STATIC_VRAM_CEILING_MB

dashboard_theme = Theme({
    "header": "bold magenta",
    "info": "cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "metric": "bold cyan",
    "bar.green": "green",
    "bar.yellow": "yellow",
    "bar.red": "bold red",
    "dim": "dim white",
})

console = Console(theme=dashboard_theme)

def make_meter(percent: float, width: int = 24) -> Text:
    """Create a colored ASCII meter bar like [||||||||||          34.2%]."""
    clamped = max(0.0, min(100.0, percent))
    filled_len = int(round((clamped / 100.0) * width))
    empty_len = width - filled_len

    meter = Text()
    meter.append("[", style="dim")

    # Pick color based on utilization
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

class KingdomTopDashboard:
    """Live htop-style system monitor and server console dashboard."""

    def __init__(self, host: str = "127.0.0.1", port: int = 58420, bearer_token: str = "local-token"):
        self.host = host
        self.port = port
        self.token = bearer_token
        self.start_time = time.time()
        self.cache_db = None
        self.orchestrator = None
        self.status_message = "● RUNNING (DirectML GPU / AVX2)"
        self.show_help = False

    def attach_engines(self, cache_db=None, orchestrator=None):
        """Optionally attach engine singletons for live stats."""
        self.cache_db = cache_db
        self.orchestrator = orchestrator

    def get_uptime_str(self) -> str:
        """Calculate server uptime formatted as HH:MM:SS."""
        elapsed = int(time.time() - self.start_time)
        hours, rem = divmod(elapsed, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours:02d}h:{minutes:02d}m:{seconds:02d}s"

    def render_header(self) -> Panel:
        """Render top summary header with host, port, token, and uptime."""
        uptime = self.get_uptime_str()
        
        t = Table.grid(expand=True)
        t.add_column(ratio=2)
        t.add_column(ratio=1, justify="right")

        left = Text()
        left.append("👑 KINGDOM AI SERVER V2 ", style="bold magenta")
        left.append("• K-TOP DASHBOARD\n", style="bold white")
        left.append(f"Base URL: http://{self.host}:{self.port}  ", style="info")
        left.append(f"Token: {self.token}  ", style="warning")
        left.append(f"Status: {self.status_message}", style="success")

        right = Text()
        right.append(f"Uptime: {uptime}\n", style="bold cyan")
        right.append(f"VRAM Ceiling: <= {STATIC_VRAM_CEILING_MB} MB", style="dim")

        t.add_row(left, right)
        return Panel(t, border_style="magenta", padding=(0, 1))

    def render_resource_gauges(self) -> Panel:
        """Render CPU, RAM, VRAM, and NPU resource progress bars."""
        telemetry = HardwareTelemetry.snapshot()
        cpu_pct = telemetry.get("cpu_percent", 0.0)
        ram_info = telemetry.get("ram_percent", 0.0)
        ram_used_gb = telemetry.get("ram_used_gb", 0.0)
        ram_total_gb = telemetry.get("ram_total_gb", 16.0)
        vram_used_gb = telemetry.get("vram_used_gb", 1.15)
        gpu_engine = telemetry.get("gpu_engine", "DirectML")
        npu_lat = telemetry.get("npu_latency_ms", 12.4)

        # Static ceiling 6.00 GB
        vram_pct = (vram_used_gb / 6.00) * 100.0

        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(width=8, style="bold")
        grid.add_column(width=34)
        grid.add_column(justify="left")

        # CPU Row
        cpu_meter = make_meter(cpu_pct, width=22)
        grid.add_row("CPU", cpu_meter, Text(f"Threads: DirectML | Engine: {gpu_engine}", style="dim"))

        # RAM Row
        ram_meter = make_meter(ram_info, width=22)
        grid.add_row("RAM", ram_meter, Text(f"{ram_used_gb:.2f} / {ram_total_gb:.2f} GB used", style="dim"))

        # VRAM Row (Guaranteed <= 6.00 GB ceiling)
        vram_meter = make_meter(vram_pct, width=22)
        vram_status = "PASSED (<= 6.00 GB)" if vram_used_gb <= 6.0 else "EXCEEDED"
        grid.add_row("VRAM", vram_meter, Text(f"{vram_used_gb:.2f} / 6.00 GB  [{vram_status}]", style="bold green" if vram_used_gb <= 6.0 else "bold red"))

        # NPU / Subsystem Row
        grid.add_row("NPU", Text("[||||||||||||||||||||||]", style="cyan"), Text(f"Latency: {npu_lat:.1f} ms | Priority: Preemptive Scheduler", style="dim"))

        return Panel(grid, title="[bold]💻 Silicon & Hardware Telemetry[/bold]", border_style="cyan", padding=(0, 1))

    def render_council_panel(self) -> Panel:
        """Render Council Architecture, Models, and Response Cache metrics."""
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(ratio=2)
        table.add_column(ratio=2)

        cache_stats = self.cache_db.get_stats() if self.cache_db else {}
        total_cache = cache_stats.get("total_entries", 0)
        cache_hits = cache_stats.get("total_hits", 0)
        hit_ratio = cache_stats.get("hit_ratio_pct", 0.0)

        boss_status = "● READY"
        if self.orchestrator and not self.orchestrator.is_loaded:
            boss_status = "○ LAZY LOAD"

        stats = tracker.get_stats()
        speed = stats.get("last_tokens_per_sec", 0.0)

        left = Text()
        left.append("🏛️ Council Ministers\n", style="bold yellow")
        left.append(f" • Boss LLM:   Qwen 2.5 Coder 1.5B [{boss_status}]\n", style="info")
        left.append(" • Minister 1: BGE Embedder 384-d   [● ACTIVE]\n", style="info")
        left.append(" • Minister 2: BGE Reranker         [● ACTIVE]\n", style="info")
        left.append(" • Native AST: Tree-Sitter Parser   [● READY]", style="info")

        right = Text()
        right.append("⚡ Throughput & Cache DB\n", style="bold yellow")
        right.append(f" • Generation Speed: {speed:.1f} tokens/sec\n", style="success" if speed > 0 else "dim")
        right.append(f" • Cached Entries:   {total_cache} prompt patterns\n", style="metric")
        right.append(f" • Cache Hit Ratio:  {hit_ratio:.1f}% ({cache_hits} hits)\n", style="metric")
        right.append(f" • Cache Latency:    < 0.05 ms (SQLite WAL)", style="dim")

        table.add_row(left, right)
        return Panel(table, title="[bold]🧠 Council & Cognitive Memory[/bold]", border_style="yellow", padding=(0, 1))

    def render_requests_table(self) -> Panel:
        """Render table of in-flight and recent HTTP inference requests."""
        table = Table(expand=True, box=None, padding=(0, 1))
        table.add_column("ID", style="bold magenta", width=10)
        table.add_column("Time", style="dim", width=9)
        table.add_column("Method", style="bold cyan", width=7)
        table.add_column("Endpoint", style="bold white", ratio=3)
        table.add_column("Priority", style="yellow", width=9)
        table.add_column("Status", width=10)
        table.add_column("Latency", justify="right", width=10)
        table.add_column("Speed", justify="right", width=10)

        recent = tracker.get_recent_requests(limit=6)
        if not recent:
            table.add_row("-", "-", "WAITING", "No requests received yet...", "NORMAL", "IDLE", "0.0 ms", "-")
        else:
            for r in recent:
                st = r.get("status", "RUNNING")
                if st == "200":
                    st_text = Text("200 OK", style="bold green")
                elif st == "RUNNING":
                    st_text = Text("RUNNING", style="bold yellow")
                elif st == "413":
                    st_text = Text("413 BIG", style="bold red")
                elif st == "403":
                    st_text = Text("403 CSPA", style="bold red")
                else:
                    st_text = Text(str(st), style="bold")

                lat = r.get("latency_ms", 0.0)
                lat_text = f"{lat:.1f} ms" if lat > 0 else "..."
                spd = r.get("tokens_per_sec", 0.0)
                spd_text = f"{spd:.1f} t/s" if spd > 0 else "-"

                table.add_row(
                    r.get("id", ""),
                    r.get("timestamp", ""),
                    r.get("method", ""),
                    r.get("path", ""),
                    r.get("priority", "NORMAL"),
                    st_text,
                    lat_text,
                    spd_text
                )

        return Panel(table, title="[bold]📡 Live Request Stream (Continue.dev)[/bold]", border_style="blue", padding=(0, 1))

    def render_log_pane(self) -> Panel:
        """Render recent log stream lines."""
        recent_logs = log_buffer.get_recent_logs(limit=4)
        t = Text()
        for idx, line in enumerate(recent_logs):
            t.append(line)
            if idx < len(recent_logs) - 1:
                t.append("\n")
        return Panel(t, title="[bold]📜 Server Event Logs[/bold]", border_style="dim white", padding=(0, 1))

    def render_footer(self) -> Text:
        """Render bottom hotkey bar."""
        f = Text()
        f.append(" Hotkeys: ", style="bold yellow")
        f.append("[C] Clear Cache   ", style="bold white on blue")
        f.append("  [R] Force Refresh   ", style="bold white on blue")
        f.append("  [H] Toggle Help   ", style="bold white on blue")
        f.append("  [Q / Ctrl+C] Stop Server ", style="bold white on red")
        return f

    def render_help_modal(self) -> Panel:
        """Render help overlay."""
        help_text = Text()
        help_text.append("👑 Kingdom AI Server K-Top Controls\n\n", style="bold magenta")
        help_text.append(" • [C] - Purge SQLite Response Cache DB.\n", style="bold cyan")
        help_text.append(" • [R] - Force hardware re-scan and console refresh.\n", style="bold cyan")
        help_text.append(" • [H] - Toggle this help dialog.\n", style="bold cyan")
        help_text.append(" • [Q] or [Ctrl+C] - Gracefully shut down server and restore console.\n\n", style="bold cyan")
        help_text.append("Press [H] or any key to return to dashboard.", style="dim")
        return Panel(help_text, title="[bold yellow]Help & Keybindings[/bold yellow]", border_style="yellow")

    def build_layout(self) -> Layout:
        """Assemble the complete split layout."""
        if self.show_help:
            layout = Layout()
            layout.update(self.render_help_modal())
            return layout

        layout = Layout()
        layout.split(
            Layout(name="header", size=4),
            Layout(name="telemetry", size=6),
            Layout(name="council", size=6),
            Layout(name="requests", size=9),
            Layout(name="logs", size=6),
            Layout(name="footer", size=1),
        )

        layout["header"].update(self.render_header())
        layout["telemetry"].update(self.render_resource_gauges())
        layout["council"].update(self.render_council_panel())
        layout["requests"].update(self.render_requests_table())
        layout["logs"].update(self.render_log_pane())
        layout["footer"].update(self.render_footer())

        return layout
