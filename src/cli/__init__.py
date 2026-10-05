"""
Kingdom AI Server - CLI Package (DEPRECATED in V3).

The legacy Rich Terminal UI (terminal_ui.py) and K-Top Dashboard (server_dashboard.py)
have been decommissioned in favor of Kingdom AI Studio V3 Slint Native Desktop GUI (main.py).
Lightweight deprecation stubs are maintained for backwards compatibility.
"""
from src.cli.terminal_ui import KingdomCLI
from src.cli.server_dashboard import KingdomTopDashboard, make_meter

__all__ = ["KingdomCLI", "KingdomTopDashboard", "make_meter"]
