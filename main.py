"""
Kingdom AI Server - Pure Python Server Launcher.
Starts the FastAPI OpenAI Server on http://127.0.0.1:58420 and auto-opens the Open WebUI in default browser.
Usage:
    python main.py
"""
import sys
import os
import webbrowser
import uvicorn

# Enforce UTF-8 console output encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def start_server():
    print("======================================================================")
    print(" 👑 KINGDOM AI SERVER & OPEN WEBUI (Enterprise Edition) • v1.0.0")
    print(" Dedicated Local OpenAI-Compatible Server for Continue.dev & WebUI")
    print(" Status: ● ACTIVE  |  Endpoint: http://127.0.0.1:58420")
    print("======================================================================")
    
    # Auto-launch default browser to Open WebUI
    try:
        webbrowser.open("http://127.0.0.1:58420")
    except Exception:
        pass

    # Start FastAPI Uvicorn Server
    uvicorn.run("kingdom_server.server.app:app", host="127.0.0.1", port=58420, reload=False)

if __name__ == "__main__":
    start_server()
