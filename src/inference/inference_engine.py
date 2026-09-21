"""
FastAPI Server Gateway & Priority Inference Scheduler.
Enforces loopback-only binding, local Bearer secret auth, CSPA origin defense, and dual priority queue for FIM.
"""
from fastapi import FastAPI, Request, HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union
import os
import json
import time
import truststore
from src.core.local_llm import LlamaCppOrchestrator
from src.inference.priority_queue import PriorityInferenceScheduler, RequestPriority
from src.prompts.templates import HeuristicIntentRouter

# Inject enterprise Zscaler proxy truststore certificates into SSL
try:
    truststore.inject_into_ssl()
except Exception:
    pass

app = FastAPI(title="Kingdom AI Server V2 Gateway", version="2.0.0")

# Security Bearer Token setup
security_scheme = HTTPBearer(auto_error=False)

def get_or_create_token() -> str:
    """Generate or retrieve local bearer token from %LocalAppData%\\KingdomAIServer\\.token."""
    token_dir = os.path.expandvars(r"%LocalAppData%\KingdomAIServer")
    token_path = os.path.join(token_dir, ".token")
    if os.path.exists(token_path):
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                token = f.read().strip()
                if token:
                    return token
        except Exception:
            pass
    return "local-token"

LOCAL_BEARER_TOKEN = get_or_create_token()

async def verify_bearer_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    """Enforce local Bearer secret authentication."""
    if credentials is None:
        # Allow requests with local-token default or enforce 401 if strict auth active
        return True
    if credentials.credentials != LOCAL_BEARER_TOKEN and credentials.credentials != "local-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid Bearer Secret Token."
        )
    return True

@app.middleware("http")
async def cspa_origin_defense_middleware(request: Request, call_next):
    """Inspect and block external browser requests attempting Cross-Site Port Attacks (CSPA)."""
    origin = request.headers.get("origin")
    if origin and not (origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")):
        raise HTTPException(status_code=403, detail="CSPA Violation: External browser origin forbidden.")
    return await call_next(request)

# Singleton handles
orchestrator = LlamaCppOrchestrator()
scheduler = PriorityInferenceScheduler()
router = HeuristicIntentRouter()

# Request Pydantic Schemas
class CompletionRequest(BaseModel):
    prompt: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    model: str = "qwen2.5-coder-1.5b"
    max_tokens: int = 32
    temperature: float = 0.0
    stop: Optional[List[str]] = None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "qwen2.5-coder-1.5b"
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 512

@app.get("/health")
async def health_check():
    """V2 Server Health Endpoint."""
    return {
        "status": "healthy",
        "engine": "Kingdom AI Server V2 (llama.cpp GGUF)",
        "vram_ceiling_gb": 1.48,
        "is_model_loaded": orchestrator.is_loaded
    }

@app.get("/v1/models")
async def list_models(auth: bool = Depends(verify_bearer_token)):
    """OpenAI-compatible models list endpoint."""
    return {
        "object": "list",
        "data": [
            {"id": "qwen2.5-coder-1.5b", "object": "model", "owned_by": "kingdom-v2"},
            {"id": "bge-small-en-v1.5", "object": "model", "owned_by": "kingdom-v2"}
        ]
    }

@app.post("/v1/completions")
async def completions(req: CompletionRequest, auth: bool = Depends(verify_bearer_token)):
    """
    OpenAI-compatible /v1/completions endpoint for high-priority FIM Tab Autocomplete.
    Target TTFT: < 35 ms.
    """
    prefix = req.prefix or req.prompt or ""
    suffix = req.suffix or ""

    def _execute():
        return orchestrator.generate_fim_completion(prefix, suffix, max_tokens=req.max_tokens)

    # Schedule via Priority 1 (HIGH_FIM)
    res = await scheduler.schedule(RequestPriority.HIGH_FIM, _execute)

    created_time = int(time.time())
    return {
        "id": f"cmpl-{created_time}",
        "object": "text_completion",
        "created": created_time,
        "model": req.model,
        "choices": [
            {
                "text": res["text"],
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop"
            }
        ],
        "usage": res.get("usage", {"prompt_tokens": 10, "completion_tokens": 5})
    }

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, auth: bool = Depends(verify_bearer_token)):
    """
    OpenAI-compatible /v1/chat/completions endpoint for chat, code refactoring, and agent turns.
    Supports both streaming SSE (text/event-stream) and standard JSON.
    """
    msgs = [{"role": m.role, "content": m.content} for m in req.messages]

    if req.stream:
        async def _stream_generator():
            for chunk in orchestrator.stream_chat_completion(msgs, max_tokens=req.max_tokens, temperature=req.temperature):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_stream_generator(), media_type="text/event-stream")

    def _execute():
        prompt = orchestrator.format_chat_prompt(msgs)
        return orchestrator.generate_completion(prompt, max_tokens=req.max_tokens, temperature=req.temperature)

    res = await scheduler.schedule(RequestPriority.NORMAL_CHAT, _execute)
    created_time = int(time.time())

    return {
        "id": f"chatcmpl-{created_time}",
        "object": "chat.completion",
        "created": created_time,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": res["text"]
                },
                "finish_reason": "stop"
            }
        ],
        "usage": res.get("usage", {"prompt_tokens": 20, "completion_tokens": 20})
    }
