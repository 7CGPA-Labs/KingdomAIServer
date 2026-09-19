"""
Kingdom AI Server V2 Entrypoint Launcher.
Binds FastAPI strictly to local loopback interface 127.0.0.1:58420.
"""
import uvicorn
from src.config import get_model_config

def main():
    config = get_model_config()
    server_cfg = config.get("server", {})
    host = server_cfg.get("host", "127.0.0.1")
    port = server_cfg.get("port", 58420)

    print("======================================================================")
    print(" 👑 KINGDOM AI SERVER V2 (llama.cpp GGUF Engine) • v2.0.0")
    print(f" Status: ● ACTIVE  |  Loopback Endpoint: http://{host}:{port}")
    print(" VRAM Ceiling: <= 1.48 GB (DirectML GPU / CPU AVX2 Fallback)")
    print("======================================================================")

    uvicorn.run("src.inference.inference_engine:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
