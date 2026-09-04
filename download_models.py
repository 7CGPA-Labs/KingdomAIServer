"""
Standalone script to download and auto-provision all 9 model weights for Kingdom AI Server.
Usage:
    python download_models.py
"""
import sys
import os
import subprocess
from pathlib import Path

# Auto-detect and switch to virtual environment if dependencies are missing
try:
    import rich
    import truststore
    import huggingface_hub
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

from kingdom_server.utils.downloader import ModelDownloader

if __name__ == "__main__":
    print("======================================================================")
    print(" 📦 KINGDOM AI SERVER - MODEL WEIGHTS AUTO-PROVISIONER")
    print("======================================================================")
    downloader = ModelDownloader()
    downloader.auto_provision_missing()
