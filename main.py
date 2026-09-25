"""
Kingdom AI Server V2 - Main Entrypoint Launcher.
Starts the FastAPI OpenAI Server on http://127.0.0.1:58420 and auto-opens the Open WebUI in default browser.
Usage:
    python main.py
"""
import sys
import subprocess
import webbrowser
from pathlib import Path

# Auto-detect and switch to virtual environment if uvicorn is missing in active Python interpreter
try:
    import uvicorn
except ImportError:
    script_dir = Path(__file__).parent.resolve()
    current_py = Path(sys.executable).resolve()
    possible_venvs = [
        script_dir / "venv" / "Scripts" / "python.exe",
        script_dir.parent / "venv" / "Scripts" / "python.exe",
        script_dir / "venv" / "bin" / "python",
        script_dir.parent / "venv" / "bin" / "python",
    ]
    for venv_py in possible_venvs:
        if venv_py.exists() and venv_py.resolve() != current_py:
            print(f"🔄 Switching to virtual environment Python: {venv_py}")
            cmd = [str(venv_py), str(Path(__file__).resolve())] + sys.argv[1:]
            sys.exit(subprocess.call(cmd))

    print(f"❌ Error: 'uvicorn' is not installed in Python environment ({sys.executable}).")
    print("Please install requirements: pip install -e .")
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
from src.config import get_model_config
from src.inference.inference_engine import LOCAL_BEARER_TOKEN

def start_server():
    config = get_model_config()
    server_cfg = config.get("server", {})
    host = server_cfg.get("host", "127.0.0.1")
    port = server_cfg.get("port", 58420)
    token = LOCAL_BEARER_TOKEN

    print("======================================================================")
    print(" 👑 KINGDOM AI SERVER (V2 Headless Edition) • v2.0.0")
    print(" Dedicated Local OpenAI-Compatible Server for Continue.dev")
    print("======================================================================")
    print(" ● Server Status: ACTIVE")
    print(f" ● Base URL:      http://{host}:{port}")
    print(f" ● Bearer Token:  {token}")
    print(" ● VRAM Ceiling:  <= 6.00 GB (DirectML GPU / CPU AVX2 Fallback)")
    print("----------------------------------------------------------------------")
    print(" 📡 Active API Endpoints:")
    print(f"   • Chat Completions: POST http://{host}:{port}/v1/chat/completions")
    print(f"   • Text Embeddings:  POST http://{host}:{port}/v1/embeddings")
    print(f"   • Context Rerank:   POST http://{host}:{port}/v1/rerank")
    print(f"   • Inline Edits:     POST http://{host}:{port}/v1/edits")
    print(f"   • Workspace Apply:  POST http://{host}:{port}/v1/apply")
    print(f"   • WebUI Console:    GET  http://{host}:{port}/")
    print("----------------------------------------------------------------------")
    print(" 🏛️ Council Architecture:")
    print("   • Boss LLM:        Qwen 2.5 Coder 1.5B GGUF")
    print("   • Minister 1:      BGE Embedder (Semantic Vector Search)")
    print("   • Minister 2:      BGE Reranker (Cross-Encoder Re-ranking)")
    print("   • Native Engine:   Tree-Sitter AST & Heuristic Router")
    print("======================================================================")

    def _open_browser():
        time.sleep(1.5)
        try:
            webbrowser.open(f"http://{host}:{port}")
        except Exception:
            pass

    threading.Thread(target=_open_browser, daemon=True).start()

    # Start FastAPI Uvicorn Server
    uvicorn.run("src.inference.inference_engine:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    start_server()
