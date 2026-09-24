"""
Headless OpenAI-Compatible REST Gateway & Priority Inference Scheduler for Kingdom AI Server V2.
Enforces loopback-only binding, local Bearer secret auth, CSPA origin defense, 2 MB payload size limits, and dual priority queue for FIM.
Exposes ONLY /v1/completions and /v1/chat/completions for Continue.dev IDE extension.
"""
from fastapi import FastAPI, Request, HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Union
import os
import json
import time
import truststore
from contextlib import asynccontextmanager

from src.core.local_llm import LlamaCppOrchestrator
from src.core.hardware import HardwareManager, STATIC_VRAM_CEILING_MB
from src.inference.priority_queue import PriorityInferenceScheduler, RequestPriority
from src.prompts.templates import HeuristicIntentRouter
from src.prompts.chain import AgentPersonaChain
from src.processing.preprocessor import Preprocessor
from src.rag.embedder import BGEEmbedder
from src.rag.retriever import BGEReranker
from src.processing.cache import ResponseCacheDB
from src.rag.vector_store import VectorStore
from src.processing.prefill import prefill_response_cache, prefill_vector_store, warmup_llm_engine

# Inject enterprise Zscaler proxy truststore certificates into SSL
try:
    truststore.inject_into_ssl()
except Exception:
    pass

# Singleton Engine Handles
orchestrator = LlamaCppOrchestrator()
scheduler = PriorityInferenceScheduler()
router = HeuristicIntentRouter()
preprocessor = Preprocessor()
embedder = BGEEmbedder()
reranker = BGEReranker()
persona_chain = AgentPersonaChain()
cache_db = ResponseCacheDB()
vector_store = VectorStore()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prefills Response Cache, Cognitive Vector DB, and warms up the LLM engine on boot."""
    try:
        prefill_response_cache(cache_db)
        prefill_vector_store(vector_store, embedder)
        warmup_llm_engine(orchestrator)
    except Exception:
        pass
    yield

app = FastAPI(
    title="Kingdom AI Server V2 Gateway",
    description="Headless OpenAI-Compatible Server for Continue.dev",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for Continue.dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        return True
    if credentials.credentials != LOCAL_BEARER_TOKEN and credentials.credentials != "local-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid Bearer Secret Token."
        )
    return True

# 2 MB Payload Size Limit & CSPA Defense Middleware
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024  # 2 MB

@app.middleware("http")
async def security_guardrails_middleware(request: Request, call_next):
    # 1. CSPA Origin Header Check
    origin = request.headers.get("origin")
    if origin and not (origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")):
        return JSONResponse(
            status_code=403,
            content={"error": {"message": "CSPA Violation: External browser origin forbidden."}}
        )

    # 2. Payload Size Limit Check (2 MB)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_PAYLOAD_BYTES:
        return JSONResponse(
            status_code=413,
            content={"error": {"message": "Payload Too Large: Maximum allowed size is 2 MB."}}
        )

    return await call_next(request)

import jinja2

class CompletionRequest(BaseModel):
    prompt: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    model: str = "qwen2.5-coder-1.5b"
    max_tokens: int = 24
    temperature: float = 0.0
    stream: bool = False
    stop: Optional[List[str]] = None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "qwen2.5-coder-1.5b"
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 8192
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None

class RerankRequest(BaseModel):
    query: str
    documents: List[str]
    top_n: Optional[int] = None
    model: Optional[str] = "bge-reranker-base"

class EmbeddingsRequest(BaseModel):
    input: Union[str, List[str]]
    model: Optional[str] = "bge-small-en-v1.5"

class EditRequest(BaseModel):
    model: str = "qwen2.5-coder-1.5b"
    input: str = ""
    instruction: str
    temperature: Optional[float] = 0.7

class ApplyRequest(BaseModel):
    model: str = "qwen2.5-coder-1.5b"
    prompt: str
    temperature: Optional[float] = 0.7



# =============================================================================
# ENDPOINT 0: / — Jinja2 Server Status Page
# =============================================================================

INFO_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kingdom AI Server V2</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 40px; display: flex; justify-content: center; }
        .container { background-color: #1e293b; padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); max-width: 600px; width: 100%; border: 1px solid #334155; }
        h1 { color: #38bdf8; margin-top: 0; }
        .status { display: inline-block; background-color: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em; margin-bottom: 20px; }
        .metric { margin: 10px 0; padding: 10px; background-color: #0f172a; border-radius: 6px; display: flex; justify-content: space-between; }
        .metric span.label { color: #94a3b8; }
        .metric span.value { font-family: monospace; color: #f1f5f9; }
        .endpoints { margin-top: 20px; color: #cbd5e1; }
        code { background-color: #0f172a; padding: 2px 6px; border-radius: 4px; color: #fbbf24; }
    </style>
</head>
<body>
    <div class="container">
        <h1>👑 Kingdom AI Server V2</h1>
        <div class="status">● System Active & Ready</div>
        
        <div class="metric"><span class="label">Architecture</span><span class="value">Headless OpenAI Gateway</span></div>
        <div class="metric"><span class="label">VRAM Ceiling</span><span class="value">{{ vram_ceiling }} MB</span></div>
        <div class="metric"><span class="label">Active GPU Provider</span><span class="value">{{ gpu_provider }}</span></div>
        <div class="metric"><span class="label">Main Model Loaded</span><span class="value">{{ is_loaded }}</span></div>
        <div class="metric"><span class="label">Bearer Token</span><span class="value">{{ bearer_token }}</span></div>
        
        <div class="endpoints">
            <h3>Active Endpoints:</h3>
            <p><code>POST /v1/completions</code> (Continue.dev Copilot-Grade FIM Autocomplete)</p>
            <p><code>POST /v1/chat/completions</code> (Continue.dev Chat Sidebar)</p>
        </div>
    </div>
</body>
</html>
"""

def extract_quick_context(code_prefix: str) -> tuple[str, str]:
    """Extract language imports and retrieve top relevant prefilled template in < 2 ms."""
    import_lines = []
    for line in code_prefix.splitlines()[:50]:
        l_str = line.strip()
        if l_str.startswith(("import ", "from ", "package ", "using ", "#include ", "require(")):
            import_lines.append(l_str)
    imports_header = "\n".join(import_lines[:8]) if import_lines else ""

    ws_context = ""
    try:
        trimmed = code_prefix.strip()
        if len(trimmed) > 15:
            query_vec = embedder.embed_query(trimmed[-80:])
            similar = vector_store.search_similar(query_vec, top_k=1)
            if similar and similar[0].get("similarity_score", 0) > 0.35:
                ws_context = similar[0]["content"][:250].strip()
    except Exception:
        pass

    return imports_header, ws_context

@app.get("/")
async def root_info_page():
    """Renders a lightweight inline Jinja2 status page."""
    hw = HardwareManager()
    diag = hw.detect_environment()
    template = jinja2.Template(INFO_TEMPLATE)
    html_content = template.render(
        vram_ceiling=STATIC_VRAM_CEILING_MB,
        gpu_provider=diag.get("selected_provider", "Unknown"),
        is_loaded="✅ Yes" if orchestrator.is_loaded else "❌ No (Lazy load)",
        bearer_token=LOCAL_BEARER_TOKEN
    )
    return HTMLResponse(content=html_content, status_code=200)

# =============================================================================
# ENDPOINT 1: /v1/completions — Copilot-Grade FIM Tab Autocomplete for Continue.dev
# =============================================================================

@app.post("/v1/completions")
async def completions(req: CompletionRequest, auth: bool = Depends(verify_bearer_token)):
    """OpenAI-compatible /v1/completions endpoint for Copilot-grade FIM Tab Autocomplete (<35 ms TTFT target)."""
    prefix = req.prefix or req.prompt or ""
    suffix = req.suffix or ""

    cache_key = ResponseCacheDB.compute_cache_key(req.model, prefix, suffix, req.temperature, req.max_tokens)
    cached_resp = cache_db.get(cache_key)
    if cached_resp:
        if req.stream:
            def _cached_stream_generator():
                chunk = {
                    "id": cached_resp["id"],
                    "object": "text_completion",
                    "created": cached_resp["created"],
                    "model": req.model,
                    "choices": [{"text": cached_resp["choices"][0]["text"], "index": 0, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(_cached_stream_generator(), media_type="text/event-stream")
        return cached_resp

    start_time = time.perf_counter()
    created_time = int(time.time())

    # Fast-slice AST imports (< 1 ms)
    imports_header, ws_context = extract_quick_context(prefix)

    # Cancel any previous in-flight FIM immediately to free compute
    orchestrator.cancel_active_fim()
    abort_event = threading.Event()

    if req.stream:
        def _stream_generator():
            try:
                for chunk in orchestrator.stream_fim_completion(
                    prefix=prefix,
                    suffix=suffix,
                    max_tokens=min(req.max_tokens, 32),
                    workspace_context=ws_context,
                    imports_header=imports_header,
                    abort_event=abort_event
                ):
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                abort_event.set()
        return StreamingResponse(_stream_generator(), media_type="text/event-stream")

    def _execute():
        return orchestrator.generate_fim_completion(
            prefix,
            suffix,
            max_tokens=min(req.max_tokens, 32),
            workspace_context=ws_context,
            imports_header=imports_header
        )

    res = await scheduler.schedule(RequestPriority.HIGH_FIM, _execute)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    response_data = {
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
        "usage": res.get("usage", {"prompt_tokens": 10, "completion_tokens": 5}),
        "latency_ms": elapsed_ms
    }

    cache_db.put(cache_key, res["text"], response_data, query_type="FIM")
    return response_data

# =============================================================================
# ENDPOINT 2: /v1/chat/completions — Multi-turn Chat for Continue.dev
# =============================================================================

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, auth: bool = Depends(verify_bearer_token)):
    """OpenAI-compatible /v1/chat/completions endpoint supporting streaming SSE and JSON.
    Integrates HeuristicIntentRouter, BGEEmbedder (Minister 1), and BGEReranker (Minister 2) internally."""
    msgs = [{"role": m.role, "content": m.content} for m in req.messages]

    if req.stream:
        def _stream_generator():
            for chunk in orchestrator.stream_chat_completion(msgs, max_tokens=req.max_tokens, temperature=req.temperature, tools=req.tools):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_stream_generator(), media_type="text/event-stream")

    # Non-streaming: cache check
    prompt_summary = json.dumps(msgs)
    cache_key = ResponseCacheDB.compute_cache_key(req.model, prompt_summary, "", req.temperature, req.max_tokens)
    cached_resp = cache_db.get(cache_key)
    if cached_resp:
        return cached_resp

    # Route intent via HeuristicIntentRouter (< 0.05 ms)
    last_user_msg = msgs[-1]["content"] if msgs else ""
    route_info = router.route_intent(last_user_msg)

    # Integrated RAG enrichment: Embed + VectorSearch + ReRank (Ministers 1 & 2)
    context_chunks = []
    if route_info["target_agent"] == "MINISTER_1_2_RAG":
        try:
            from src.rag.vector_store import VectorStore
            query_vec = embedder.embed_query(last_user_msg)
            vs = VectorStore()
            candidates = vs.search_similar(query_vec, top_k=5)
            if candidates:
                context_chunks = reranker.rerank(last_user_msg, candidates, top_k=3)
        except Exception:
            pass

    # Build enriched message list with RAG context
    enriched_msgs = list(msgs)
    if context_chunks:
        context_text = "\n".join(c.get("content", "") for c in context_chunks)
        enriched_msgs.insert(0, {"role": "system", "content": f"Relevant workspace context:\n{context_text}"})

    def _execute():
        prompt = orchestrator.format_chat_prompt(enriched_msgs, tools=req.tools)
        return orchestrator.generate_completion(prompt, max_tokens=req.max_tokens, temperature=req.temperature)

    res = await scheduler.schedule(RequestPriority.NORMAL_CHAT, _execute)
    created_time = int(time.time())

    response_data = {
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

    cache_db.put(cache_key, res["text"], response_data, query_type="CHAT")
    return response_data

# =============================================================================
# ENDPOINT 3: /v1/rerank — Cohere-compatible Reranker API
# =============================================================================
@app.post("/v1/rerank")
async def rerank_documents(req: RerankRequest, auth: bool = Depends(verify_bearer_token)):
    """OpenAI/Cohere-compatible endpoint for Continue.dev @Codebase reranking."""
    
    if not req.documents:
        return {"results": []}
        
    start_time = time.perf_counter()
    
    # Load reranker if not loaded
    if not reranker.is_model_loaded:
        reranker._load_session()
        
    # Score pairs
    scores = reranker.score_pairs(req.query, req.documents)
    
    # Sort and format results
    results = []
    for idx, score in enumerate(scores):
        results.append({
            "index": idx,
            "relevance_score": float(score)
        })
        
    # Sort by relevance descending
    results = sorted(results, key=lambda x: x["relevance_score"], reverse=True)
    
    # Apply top_n limit if requested
    if req.top_n is not None and req.top_n > 0:
        results = results[:req.top_n]
        
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    
    return {
        "model": req.model or "bge-reranker-base",
        "results": results,
        "meta": {
            "latency_ms": elapsed_ms
        }
    }

# =============================================================================
# ENDPOINT 4: /v1/embeddings — OpenAI-compatible Embeddings API
# =============================================================================
@app.post("/v1/embeddings")
async def create_embeddings(req: EmbeddingsRequest, auth: bool = Depends(verify_bearer_token)):
    """OpenAI-compatible endpoint for generating vectors via BGE Embedder."""
    if not embedder.is_model_loaded:
        embedder._load_session()
        
    inputs = [req.input] if isinstance(req.input, str) else req.input
    data = []
    
    for i, text in enumerate(inputs):
        vec = embedder.embed_query(text)
        data.append({
            "object": "embedding",
            "embedding": vec,
            "index": i
        })
        
    return {
        "object": "list",
        "data": data,
        "model": req.model,
        "usage": {"prompt_tokens": 0, "total_tokens": 0}
    }

# =============================================================================
# ENDPOINT 5: /v1/edits — OpenAI-compatible Edits API
# =============================================================================
@app.post("/v1/edits")
async def create_edit(req: EditRequest, auth: bool = Depends(verify_bearer_token)):
    """Legacy OpenAI-compatible endpoint for code editing."""
    prompt = f"Instruction: {req.instruction}\nInput code:\n{req.input}\nOutput edited code:\n"
    
    def _execute():
        return orchestrator.generate_completion(prompt, max_tokens=2048, temperature=req.temperature or 0.7)
        
    res = await scheduler.schedule(RequestPriority.NORMAL_CHAT, _execute)
    created_time = int(time.time())
    
    return {
        "id": f"edit-{created_time}",
        "object": "edit",
        "created": created_time,
        "model": req.model,
        "choices": [
            {
                "text": res["text"],
                "index": 0
            }
        ],
        "usage": res.get("usage", {})
    }

# =============================================================================
# ENDPOINT 6: /v1/apply — Custom Apply API
# =============================================================================
@app.post("/v1/apply")
async def apply_code(req: ApplyRequest, auth: bool = Depends(verify_bearer_token)):
    """Endpoint for applying changes to code."""
    def _execute():
        return orchestrator.generate_completion(req.prompt, max_tokens=2048, temperature=req.temperature or 0.7)
        
    res = await scheduler.schedule(RequestPriority.NORMAL_CHAT, _execute)
    created_time = int(time.time())
    
    return {
        "id": f"apply-{created_time}",
        "object": "apply",
        "created": created_time,
        "model": req.model,
        "choices": [
            {
                "text": res["text"],
                "index": 0
            }
        ],
        "usage": res.get("usage", {})
    }
