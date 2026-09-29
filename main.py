"""
Kingdom AI Studio V3 - Main Desktop Entrypoint.
Boots the standalone desktop AI programming studio powered by Slint GUI.
100% on-device in-process execution with zero server overhead.

Usage:
    python main.py             # Launch Kingdom AI Studio V3 Desktop GUI
    python main.py --server    # Launch legacy V2 HTTP/OpenAI server (deprecated)
"""
import sys
import os
from pathlib import Path

# Enforce UTF-8 console output encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _attach_interactive_desktop():
    """Ensures the process and thread are attached to the interactive user desktop on Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Connect process to interactive window station WinSta0
            h_winsta = user32.OpenWindowStationW("WinSta0", False, 0x10000000)
            if h_winsta:
                user32.SetProcessWindowStation(h_winsta)
            # Connect thread to interactive Default desktop
            h_desk = user32.OpenDesktopW("Default", 0, False, 0x10000000)
            if h_desk:
                user32.SetThreadDesktop(h_desk)
        except Exception:
            pass


def launch_studio():
    """Boots the Slint-powered Kingdom AI Studio V3 Desktop GUI."""
    _attach_interactive_desktop()
    print("======================================================================")
    print(" 👑 KINGDOM AI STUDIO V3 • GOOGLE ANTIGRAVITY GUI EDITION")
    print(" Standalone On-Device AI Coding Assistant (Slint Native Desktop GUI)")
    print("======================================================================")
    print(" ● Execution Mode:  100% In-Process (Zero-Server Architecture)")
    print(" ● VRAM Budget:     <= 6.00 GB (Strict Hardware Safety Ceiling)")
    print(" ● UI Engine:       Slint Declarative Native GUI (60 FPS)")
    print("----------------------------------------------------------------------")

    from src.gui import AppController
    controller = AppController(auto_start_telemetry=True)
    print(" Launching Kingdom AI Studio desktop window...")
    controller.run()


def launch_legacy_server():
    """Fallback launcher for legacy HTTP server (deprecated)."""
    try:
        import uvicorn
        from src.config import get_model_config
        from src.inference.inference_engine import LOCAL_BEARER_TOKEN

        config = get_model_config()
        server_cfg = config.get("server", {})
        host = server_cfg.get("host", "127.0.0.1")
        port = server_cfg.get("port", 58420)
        token = LOCAL_BEARER_TOKEN

        print("======================================================================")
        print(" 👑 KINGDOM AI SERVER (Legacy Headless Edition - Deprecated)")
        print(f" Base URL: http://{host}:{port} | Bearer: {token}")
        print(" Note: Kingdom AI Studio V3 desktop GUI is the recommended interface.")
        print("======================================================================")
        uvicorn.run("src.inference.inference_engine:app", host=host, port=port, reload=False)
    except ImportError:
        print("❌ Error: uvicorn is not installed in the active environment.")
        print("To run the desktop studio, use: python main.py")
        sys.exit(1)


def main():
    if "--server" in sys.argv or "--headless" in sys.argv or os.environ.get("KINGDOM_LEGACY_SERVER") == "1":
        launch_legacy_server()
    else:
        launch_studio()


if __name__ == "__main__":
    main()
