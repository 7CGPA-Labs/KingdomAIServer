"""
FastAPI Server for Kingdom AI Server - OpenAI Compatible API endpoints.
Running on http://127.0.0.1:58420
"""
import time
import json
import uuid
import logging
from typing import List, Dict, Any, Optional, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from kingdom_server.core.orchestrator import KingdomOrchestrator
from kingdom_server.server.sse import create_sse_response
from kingdom_server.utils.telemetry import HardwareTelemetry
from kingdom_server.utils.verifier import ModelVerifier
from kingdom_server.utils import get_log_path

# Configure file logging to %LocalAppData%\KingdomAIServer\server.log
log_file = get_log_path()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(log_file), mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("kingdom.server")

# Global Orchestrator instance
orchestrator: Optional[KingdomOrchestrator] = None

def get_orchestrator() -> KingdomOrchestrator:
    global orchestrator
    if orchestrator is None:
        logger.info("Initializing Kingdom AI Server Orchestrator...")
        orchestrator = KingdomOrchestrator()
    return orchestrator

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_orchestrator()
    logger.info("Kingdom AI Server startup sequence complete. Ready on http://127.0.0.1:58420")
    yield

# Instantiate FastAPI application
app = FastAPI(
    title="Kingdom AI Server",
    description="Dedicated Local OpenAI-Compatible Server for Continue.dev",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for Continue.dev VS Code Extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request / Response Pydantic Models
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "qwen2.5-coder-1.5b"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    stream: Optional[bool] = True

class CompletionRequest(BaseModel):
    model: Optional[str] = "granite-code-128m"
    prompt: Optional[str] = ""
    prefix: Optional[str] = None
    suffix: Optional[str] = ""
    max_tokens: Optional[int] = 16

class EmbeddingRequest(BaseModel):
    model: Optional[str] = "bge-small-en-v1.5"
    input: Union[str, List[str]]

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint (SSE streaming delta chunks or JSON)."""
    orch = get_orchestrator()
    dict_messages = [{"role": m.role, "content": m.content} for m in req.messages]

    if req.stream:
        stream_gen = orch.generate_chat_stream(
            messages=dict_messages,
            model=req.model or "qwen2.5-coder-1.5b",
            temperature=req.temperature or 0.7
        )
        return create_sse_response(stream_gen)
    else:
        # Non-streaming JSON response
        full_content = ""
        async for chunk in orch.generate_chat_stream(dict_messages, model=req.model or "qwen2.5-coder-1.5b", temperature=req.temperature or 0.7):
            if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                try:
                    data = json.loads(chunk[6:])
                    delta = data["choices"][0]["delta"].get("content", "")
                    full_content += delta
                except Exception:
                    pass

        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.model or "qwen2.5-coder-1.5b",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": full_content},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": sum(len(m.content.split()) for m in req.messages),
                "completion_tokens": len(full_content.split()),
                "total_tokens": sum(len(m.content.split()) for m in req.messages) + len(full_content.split())
            }
        }

@app.post("/v1/completions")
async def fast_completions(req: CompletionRequest):
    """Fast single-line tab autocomplete via Minister 5 (<30ms)."""
    orch = get_orchestrator()
    prefix = req.prefix if req.prefix is not None else req.prompt or ""
    suffix = req.suffix or ""
    
    start_t = time.time()
    completion_text = orch.fast_autocomplete(prefix, suffix)
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    return {
        "id": f"cmpl-{uuid.uuid4().hex[:12]}",
        "object": "text_completion",
        "created": int(time.time()),
        "model": "granite-code-128m",
        "choices": [{
            "text": completion_text,
            "index": 0,
            "logprobs": None,
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": len(prefix.split()),
            "completion_tokens": len(completion_text.split()),
            "total_tokens": len(prefix.split()) + len(completion_text.split())
        },
        "latency_ms": elapsed_ms
    }

@app.post("/v1/embeddings")
async def embeddings(req: EmbeddingRequest):
    """384-dim float vectors via Minister 2."""
    orch = get_orchestrator()
    vecs = orch.create_embeddings(req.input)
    data = []
    for idx, vec in enumerate(vecs):
        data.append({
            "object": "embedding",
            "embedding": vec,
            "index": idx
        })

    return {
        "object": "list",
        "data": data,
        "model": req.model or "bge-small-en-v1.5",
        "usage": {
            "prompt_tokens": sum(len(str(x).split()) for x in (req.input if isinstance(req.input, list) else [req.input])),
            "total_tokens": sum(len(str(x).split()) for x in (req.input if isinstance(req.input, list) else [req.input]))
        }
    }

@app.get("/health")
async def health_check():
    """Real-time JSON hardware telemetry and model silicon tier status."""
    orch = get_orchestrator()
    telemetry = HardwareTelemetry.snapshot()
    verifier = ModelVerifier()
    summary = verifier.get_summary()

    tiers = orch.hardware_engine.get_active_tiers()

    model_status = orch.get_model_status() if orch else {}

    return {
        "status": "active",
        "version": "1.0.0",
        "address": "http://127.0.0.1:58420",
        "telemetry": telemetry,
        "silicon_tiers": tiers,
        "models": {
            "total": summary["total"],
            "online": summary["valid"],
            "all_healthy": summary["all_healthy"],
            "loaded_status": model_status
        },
        "vault": orch.memory_vault.get_stats() if orch else {}
    }
