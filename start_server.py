import sys
import subprocess
from pathlib import Path

# Auto-detect and switch to virtual environment if uvicorn is missing in active Python interpreter
try:
    import uvicorn
except ImportError:
    script_dir = Path(__file__).parent.resolve()
    current_py = Path(sys.executable).resolve()
    possible_venvs = [
        script_dir.parent / "venv" / "Scripts" / "python.exe",
        script_dir / "venv" / "Scripts" / "python.exe",
        script_dir.parent / "venv" / "bin" / "python",
        script_dir / "venv" / "bin" / "python",
    ]
    for venv_py in possible_venvs:
        if venv_py.exists() and venv_py.resolve() != current_py:
            print(f"🔄 Switching to virtual environment Python: {venv_py}")
            cmd = [str(venv_py), str(Path(__file__).resolve())] + sys.argv[1:]
            sys.exit(subprocess.call(cmd))

    print(f"❌ Error: 'uvicorn' is not installed in Python environment ({sys.executable}).")
    print("Please install requirements: pip install -e .")
    sys.exit(1)

from main import start_server

if __name__ == "__main__":
    start_server()
