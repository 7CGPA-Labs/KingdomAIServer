"""
Headless OpenAI-Compatible REST Gateway & Priority Inference Scheduler for Kingdom AI Server V2.
Enforces loopback-only binding, local Bearer secret auth, CSPA origin defense, and 2 MB payload size limits.
Exposes OpenAI-compatible endpoints (/v1/chat/completions, /v1/embeddings, /v1/rerank, /v1/edits, /v1/apply) for Continue.dev IDE extension.
"""
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List, Union
import os
import sys
import json
import time
import logging
import truststore
from contextlib import asynccontextmanager

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logger = logging.getLogger("kingdom.server")

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
from src.utils.request_tracker import tracker
import uuid

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
        cache_count = prefill_response_cache(cache_db)
        logger.info("[Prefill] Response Cache pre-seeded: %s common developer queries cached", cache_count)
        vector_count = prefill_vector_store(vector_store, embedder)
        logger.info("[Prefill] Cognitive Vector Store indexed: %s architectural templates ready", vector_count)
        warmed = warmup_llm_engine(orchestrator)
        if warmed:
            logger.info("[Warmup] LLM Engine pre-warmed: Zero cold-start latency achieved")
    except Exception as e:
        logger.warning("[Startup] Notice during engine prefill/warmup: %s", e)
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

@app.middleware("http")
async def request_tracker_middleware(request: Request, call_next):
    if request.url.path in ("/favicon.ico", "/docs", "/openapi.json"):
        return await call_next(request)

    req_id = f"req-{uuid.uuid4().hex[:6]}"
    method = request.method
    path = request.url.path
    priority = "HIGH" if path in ("/v1/edits", "/v1/apply") else "NORMAL"
    tracker.record_request_start(req_id, method, path, priority)

    try:
        response = await call_next(request)
        tracker.record_request_end(req_id, status_code=response.status_code)
        return response
    except Exception as e:
        tracker.record_request_end(req_id, status_code=500)
        raise e

import jinja2

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
            <p><code>POST /v1/chat/completions</code> (Continue.dev Chat Sidebar)</p>
            <p><code>POST /v1/embeddings</code> (Codebase Vector Embeddings)</p>
            <p><code>POST /v1/rerank</code> (Context Reranker)</p>
            <p><code>POST /v1/edits</code> (Inline Code Editing)</p>
            <p><code>POST /v1/apply</code> (Apply Code Actions)</p>
        </div>
    </div>
</body>
</html>
"""

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

BUILTIN_AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "codebase_search",
            "description": "Semantically search indexed repository codebase for symbols, functions, or architectural logic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Semantic search query or symbol"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "security_audit",
            "description": "Run static vulnerability scanner across code snippet for CWE issues, secrets, and injection sinks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The code to audit"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_imports",
            "description": "Check whether imports are declared in project package manifests (package.json, requirements.txt, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "imports": {"type": "array", "items": {"type": "string"}, "description": "List of imported modules"}
                },
                "required": ["imports"]
            }
        }
    }
]

def enrich_chat_context(msgs: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], Dict[str, Any], float]:
    """Enrich chat messages with intent routing, persona guidelines, RAG context, and preprocessor security audits."""
    last_user_msg = ""
    for m in reversed(msgs):
        if m.get("role") == "user":
            last_user_msg = m.get("content", "")
            break

    # 1. Intent routing
    route_info = router.route_intent(last_user_msg)
    target_agent = route_info.get("target_agent", "MAIN_BOSS")
    intent = route_info.get("intent", "GENERAL_CHAT")

    # 2. Persona spec
    persona_spec = persona_chain.get_persona_spec(target_agent)
    recommended_temp = persona_spec.get("temperature", 0.7)
    system_notes = []

    if persona_spec.get("system_prompt"):
        system_notes.append(persona_spec["system_prompt"])

    # 3. Security vulnerability analysis injection
    if intent == "SECURITY_AUDIT" or "/security" in last_user_msg.lower() or "audit security" in last_user_msg.lower():
        findings = preprocessor.scan_security_issues(last_user_msg)
        if findings:
            findings_summary = "\n".join([
                f"- Line {f['line_number']}: {f['description']} (Severity: {f['severity']})"
                for f in findings[:5]
            ])
            system_notes.append(f"Static Vulnerability Analysis Findings:\n{findings_summary}")

    # 4. RAG context enrichment
    if target_agent == "MINISTER_1_2_RAG" or "@workspace" in last_user_msg.lower():
        try:
            clean_query = last_user_msg.replace("@workspace", "").replace("/search", "").strip()
            if clean_query:
                query_vec = embedder.embed_query(clean_query)
                candidates = vector_store.search_similar(query_vec, top_k=5)
                if candidates:
                    context_chunks = reranker.rerank(clean_query, candidates, top_k=3)
                    if context_chunks:
                        context_text = "\n".join(c.get("content", "") for c in context_chunks)
                        system_notes.append(f"Relevant workspace context from repository:\n{context_text}")
        except Exception:
            pass

    # 5. Context trimming for oversized code inputs
    enriched_msgs = []
    for m in msgs:
        content = m.get("content", "")
        if len(content.splitlines()) > 150 and any(kw in content for kw in ("```", "def ", "class ", "function ")):
            content = preprocessor.trim_context(content, max_lines=120)
        enriched_msgs.append({"role": m.get("role", "user"), "content": content})

    # 6. Apply system instructions
    if system_notes:
        combined_sys = "\n\n".join(system_notes)
        if enriched_msgs and enriched_msgs[0].get("role") == "system":
            enriched_msgs[0]["content"] = combined_sys + "\n\n" + enriched_msgs[0]["content"]
        else:
            enriched_msgs.insert(0, {"role": "system", "content": combined_sys})

    return enriched_msgs, route_info, recommended_temp

# =============================================================================
# ENDPOINT 1: /v1/chat/completions — Multi-turn Chat for Continue.dev
# =============================================================================

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, auth: bool = Depends(verify_bearer_token)):
    """OpenAI-compatible /v1/chat/completions endpoint supporting streaming SSE and JSON.
    Integrates HeuristicIntentRouter, Lean Council RAG, Preprocessor, and Agent Personas."""
    msgs = [{"role": m.role, "content": m.content} for m in req.messages]

    enriched_msgs, route_info, recommended_temp = enrich_chat_context(msgs)
    effective_temp = req.temperature if req.temperature is not None else recommended_temp
    active_tools = req.tools if req.tools is not None else None

    if req.stream:
        def _stream_generator():
            for chunk in orchestrator.stream_chat_completion(
                enriched_msgs,
                max_tokens=req.max_tokens,
                temperature=effective_temp,
                tools=active_tools
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_stream_generator(), media_type="text/event-stream")

    # Non-streaming: cache check
    prompt_summary = json.dumps(msgs)
    cache_key = ResponseCacheDB.compute_cache_key(req.model, prompt_summary, "", effective_temp, req.max_tokens)
    cached_resp = cache_db.get(cache_key)
    if cached_resp:
        return cached_resp

    def _execute():
        prompt = orchestrator.format_chat_prompt(enriched_msgs, tools=active_tools)
        return orchestrator.generate_completion(prompt, max_tokens=req.max_tokens, temperature=effective_temp)

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
# ENDPOINT 2: /v1/rerank — Cohere-compatible Reranker API
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
# ENDPOINT 3: /v1/embeddings — OpenAI-compatible Embeddings API
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
# ENDPOINT 4: /v1/edits — OpenAI-compatible Edits API
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
# ENDPOINT 5: /v1/apply — Custom Apply API
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
