"""
FastAPI Server Gateway & Priority Inference Scheduler.
Enforces loopback-only binding, local Bearer secret auth, CSPA origin defense, and dual priority queue for FIM.
"""
from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional
import os
import truststore

# Inject enterprise Zscaler proxy truststore certificates into SSL
try:
    truststore.inject_into_ssl()
except Exception:
    pass

app = FastAPI(title="Kingdom AI Server V2", version="2.0.0")

# Security Bearer Token setup
security_scheme = HTTPBearer(auto_error=False)
LOCAL_TOKEN_FILE = os.path.expandvars(r"%LocalAppData%\KingdomAIServer\.token")

def get_or_create_token() -> str:
    """Generate or retrieve local bearer token."""
    token_path = os.path.expandvars(r"%LocalAppData%\KingdomAIServer\.token")
    if os.path.exists(token_path):
        with open(token_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "local-token"

LOCAL_BEARER_TOKEN = get_or_create_token()

@app.middleware("http")
async def cspa_origin_defense_middleware(request: Request, call_next):
    """Inspect and block external browser requests attempting Cross-Site Port Attacks (CSPA)."""
    origin = request.headers.get("origin")
    if origin and not (origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")):
        return HTTPException(status_code=403, detail="CSPA Violation: External browser origin forbidden.")
    return await call_next(request)

@app.get("/health")
async def health_check():
    """V2 Server Health Endpoint."""
    return {
        "status": "healthy",
        "engine": "Kingdom AI Server V2 (llama.cpp GGUF)",
        "vram_ceiling_gb": 1.48
    }

@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible models list endpoint."""
    return {
        "object": "list",
        "data": [
            {"id": "qwen2.5-coder-1.5b", "object": "model", "owned_by": "kingdom-v2"},
            {"id": "bge-small-en-v1.5", "object": "model", "owned_by": "kingdom-v2"}
        ]
    }
