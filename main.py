"""
Entry point for kingdom.exe standalone executable binary and CLI.
"""
import sys
import io

# Ensure UTF-8 output encoding on Windows legacy consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from kingdom_server.cli.commands import app

if __name__ == "__main__":
    app()
