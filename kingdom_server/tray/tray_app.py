"""
Windows System Tray integration using pystray and Pillow.
"""
import os
import sys
import subprocess
import threading
import logging
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
from kingdom_server.utils import get_base_dir, get_models_dir, get_log_path
from kingdom_server.core.memory_vault import MemoryVault

logger = logging.getLogger("kingdom.tray")

def create_tray_icon_image():
    """Generates a dynamic 64x64 crown icon image."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw gold crown icon background & accent
    draw.polygon([(10, 50), (10, 24), (22, 36), (32, 14), (42, 36), (54, 24), (54, 50)], fill=(255, 215, 0))
    draw.rectangle([10, 48, 54, 54], fill=(218, 165, 32))
    # Small gem accents
    draw.ellipse([30, 18, 34, 22], fill=(220, 20, 60))
    return img

class SystemTrayApp:
    def __init__(self, stop_callback=None):
        self.stop_callback = stop_callback
        self.icon = None

    def on_status(self, icon, item):
        try:
            import httpx
            resp = httpx.get("http://127.0.0.1:58420/health", timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                msg = f"Kingdom AI Server: ACTIVE\nCPU: {data['telemetry']['cpu_usage_percent']}%\nRAM: {data['telemetry']['ram_used_gb']} GB\nMinisters: {data['models']['online']}/{data['models']['total']} Online"
                icon.notify(msg, title="Kingdom AI Server")
            else:
                icon.notify("Server returned non-200 status", title="Kingdom AI Server")
        except Exception:
            icon.notify("Server unreachable on port 58420", title="Kingdom AI Server Error")

    def on_open_models(self, icon, item):
        models_dir = get_models_dir()
        if sys.platform == "win32":
            os.startfile(str(models_dir))
        else:
            subprocess.Popen(["xdg-open", str(models_dir)])

    def on_view_logs(self, icon, item):
        log_file = get_log_path()
        if log_file.exists():
            if sys.platform == "win32":
                os.startfile(str(log_file))
            else:
                subprocess.Popen(["xdg-open", str(log_file)])

    def on_clear_vault(self, icon, item):
        try:
            vault = MemoryVault()
            vault.clear()
            icon.notify("Cognitive Vector Vault memory successfully cleared.", title="Kingdom Memory Vault")
        except Exception as e:
            icon.notify(f"Failed to clear vault: {e}", title="Kingdom Memory Vault")

    def on_exit(self, icon, item):
        icon.stop()
        if self.stop_callback:
            self.stop_callback()

    def run(self):
        menu = pystray.Menu(
            item("Status", self.on_status),
            item("Open Models Folder", self.on_open_models),
            item("View Logs", self.on_view_logs),
            item("Clear Vault", self.on_clear_vault),
            pystray.Menu.SEPARATOR,
            item("Exit", self.on_exit)
        )
        self.icon = pystray.Icon("kingdom_ai_server", create_tray_icon_image(), "Kingdom AI Server", menu)
        self.icon.run()

    def run_detached(self):
        t = threading.Thread(target=self.run, daemon=True)
        t.start()
        return t
