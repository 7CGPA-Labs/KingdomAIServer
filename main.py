"""
Kingdom AI Server - Pure Python Server Launcher.
Starts the FastAPI OpenAI Server on http://127.0.0.1:58420 and auto-opens the Open WebUI in default browser.
Usage:
    python main.py
"""
import sys
import os
import subprocess
import webbrowser
from pathlib import Path

# Auto-detect and switch to virtual environment if uvicorn is missing in active Python interpreter
try:
    import uvicorn
except ImportError:
    script_dir = Path(__file__).parent.resolve()
    possible_venvs = [
        script_dir.parent / "venv" / "Scripts" / "python.exe",
        script_dir / "venv" / "Scripts" / "python.exe",
        script_dir.parent / "venv" / "bin" / "python",
        script_dir / "venv" / "bin" / "python",
    ]
    for venv_py in possible_venvs:
        if venv_py.exists():
            print(f"🔄 Switching to virtual environment Python: {venv_py}")
            cmd = [str(venv_py), str(Path(__file__).resolve())] + sys.argv[1:]
            sys.exit(subprocess.call(cmd))

    print("❌ Error: 'uvicorn' is not installed in the current Python environment.")
    print("Please activate your virtual environment or run via start_server.cmd")
    sys.exit(1)

# Enforce UTF-8 console output encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import threading
import time

def start_server():
    print("======================================================================")
    print(" 👑 KINGDOM AI SERVER & OPEN WEBUI (Enterprise Edition) • v1.0.0")
    print(" Dedicated Local OpenAI-Compatible Server for Continue.dev & WebUI")
    print(" Status: ● ACTIVE  |  Endpoint: http://127.0.0.1:58420")
    print("======================================================================")
    
    # Auto-provision any missing model weights
    try:
        from kingdom_server.utils.downloader import ModelDownloader
        ModelDownloader().auto_provision_missing()
    except Exception as e:
        print(f"⚠️ Model auto-provisioning check warning: {e}")

    # Auto-launch default browser to Open WebUI after Uvicorn starts listening
    def _open_browser():
        time.sleep(1.5)
        try:
            webbrowser.open("http://127.0.0.1:58420")
        except Exception:
            pass

    threading.Thread(target=_open_browser, daemon=True).start()

    # Start FastAPI Uvicorn Server
    uvicorn.run("kingdom_server.server.app:app", host="127.0.0.1", port=58420, reload=False)

if __name__ == "__main__":
    start_server()
