import sys
import os
import subprocess
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

from main import start_server

if __name__ == "__main__":
    start_server()
