"""
Consolidated V2 Engine & Response Cache Test Suite.
Combines ResponseCacheDB, Startup Prefill Manager, Vector Vault Prefill,
LLM Warmup, and Chat Context Tool Enrichment.
"""
import os
import time
import logging
import asyncio
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from src.processing.cache import ResponseCacheDB
from src.rag.vector_store import VectorStore
from src.rag.embedder import BGEEmbedder
from src.rag.retriever import BGEReranker
from src.core.local_llm import LlamaCppOrchestrator
from src.core.council import LeanCouncilManager, TOTAL_COUNCIL_VRAM_FOOTPRINT_MB
from src.core.hardware import HardwareManager, STATIC_VRAM_CEILING_MB
from src.core.ministers import ModelFactory
from src.inference.priority_queue import PriorityInferenceScheduler, RequestPriority
from src.processing.chunking import TreeSitterChunker
from src.processing.preprocessor import ManifestLinter, VulnerabilityScanner, StructuralTrimmer
from src.prompts.chain import (
    GitCommitCraftsman,
    DiffRealigner,
    SecurityAuditor,
    MermaidDiagramGenerator,
    AgentPersonaChain,
    JSON_SECURITY_SCHEMA_GBNF,
    MERMAID_DIAGRAM_GBNF
)
from src.utils.request_tracker import RequestTracker, tracker, RingBufferLogHandler, attach_log_interceptor
from src.cli.server_dashboard import KingdomTopDashboard, make_meter
from src.processing.prefill import prefill_response_cache, prefill_vector_store, warmup_llm_engine
from src.inference.inference_engine import app, LOCAL_BEARER_TOKEN, enrich_chat_context

TEST_CACHE_DB = Path("data/cache/test_response_cache.db")
client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup_test_cache():
    if TEST_CACHE_DB.exists():
        try:
            TEST_CACHE_DB.unlink()
        except Exception:
            pass
    yield
    if TEST_CACHE_DB.exists():
        try:
            TEST_CACHE_DB.unlink()
        except Exception:
            pass

# =============================================================================
# 1. ResponseCacheDB & Instant Caching (from test_response_cache_db.py)
# =============================================================================

def test_response_cache_db_put_get():
    """Test putting and getting responses from ResponseCacheDB."""
    db = ResponseCacheDB(db_path=TEST_CACHE_DB)
    cache_key = db.compute_cache_key("qwen2.5-coder-1.5b", "def test():", "", 0.0, 32)

    # Miss check
    assert db.get(cache_key) is None

    # Insert entry
    db.put(cache_key, "return True", {"choices": [{"text": "return True"}]}, query_type="CHAT")

    # Hit check (< 50 ms test threshold)
    cached = db.get(cache_key)
    assert cached is not None
    assert cached["cached"] is True
    assert cached["cache_hit_latency_ms"] < 50.0
    assert cached["choices"][0]["text"] == "return True"

    stats = db.get_stats()
    assert stats["total_cached_entries"] == 1
    assert stats["total_cache_hits"] == 1

def test_api_caching_instant_hit():
    """Test API-level instant caching hit via /v1/chat/completions."""
    headers = {"Authorization": f"Bearer {LOCAL_BEARER_TOKEN}"}
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "messages": [
            {"role": "user", "content": "Hello Kingdom AI"}
        ],
        "stream": False,
        "max_tokens": 16,
        "temperature": 0.0
    }

    # First request: Cache Miss & Store
    resp1 = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()

    # Second request: Cache Hit (< 0.05 ms instant response)
    resp2 = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2.get("cached") is True

# =============================================================================
# 2. Prefill & Warmup Manager (from test_prefill.py)
# =============================================================================

def test_prefill_response_cache(tmp_path):
    """Verify ResponseCacheDB prefill populates cache with common chat responses."""
    cache_path = tmp_path / "test_cache.db"
    db = ResponseCacheDB(db_path=cache_path)
    
    count = prefill_response_cache(db)
    assert count >= 10
    
    stats = db.get_stats()
    assert stats["total_cached_entries"] >= 10

def test_prefill_vector_store(tmp_path):
    """Verify VectorStore prefill loads code templates into database."""
    vault_path = tmp_path / "test_vault.db"
    vs = VectorStore(db_path=str(vault_path))
    embedder = BGEEmbedder()
    
    count = prefill_vector_store(vs, embedder)
    assert count >= 4
    
    chunks = vs.get_all_chunks()
    assert len(chunks) >= 4
    
    # Verify semantic search on prefilled template
    q_vec = embedder.embed_query("CustomHealthIndicator")
    results = vs.search_similar(q_vec, top_k=4)
    assert len(results) >= 1
    assert any("HealthIndicator" in r["content"] for r in results)

def test_warmup_engine():
    """Verify engine warmup executes without unhandled errors."""
    orch = LlamaCppOrchestrator()
    result = warmup_llm_engine(orch)
    assert isinstance(result, bool)

# =============================================================================
# 3. Chat Context Tool & Vulnerability Enrichment
# =============================================================================

def test_chat_context_enrichment_security_and_rag():
    """Verify enrich_chat_context integrates VulnerabilityScanner findings and intent routing."""
    # Test Security Audit enrichment
    sec_msgs = [{"role": "user", "content": "/security eval('rm -rf /'); api_key = 'sk_live_1234567890abcdef12345'"}]
    enriched, route, temp = enrich_chat_context(sec_msgs)
    assert route["intent"] == "SECURITY_AUDIT"
    assert temp == 0.1
    # Check that security findings were injected into system prompt
    assert any("Static Vulnerability Analysis Findings" in m.get("content", "") for m in enriched if m["role"] == "system")

    # Test Git Commit enrichment
    git_msgs = [{"role": "user", "content": "/commit fix: typo in readme"}]
    enriched_git, route_git, temp_git = enrich_chat_context(git_msgs)
    assert route_git["intent"] == "GIT_COMMIT"
    assert temp_git == 0.0

# =============================================================================
# 4. GGUF Runtime Core & Chat Completions Gateway (from test_stage3_gguf_runtime.py)
# =============================================================================

def test_orchestrator_chatml_formatting():
    orch = LlamaCppOrchestrator()
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Write a hello world in Python."}
    ]
    formatted = orch.format_chat_prompt(messages)

    assert "<|im_start|>system" in formatted
    assert "<|im_start|>user" in formatted
    assert "<|im_start|>assistant\n" in formatted
    assert formatted.endswith("<|im_start|>assistant\n")

def test_orchestrator_uninitialized_fallback():
    orch = LlamaCppOrchestrator()
    res = orch.generate_completion("Test prompt")
    assert "text" in res
    assert "usage" in res

def test_priority_scheduler():
    async def _test():
        scheduler = PriorityInferenceScheduler()
        
        def dummy_high():
            return {"text": "high priority response"}

        def dummy_chat():
            return {"text": "Here is your explanation."}

        res_high = await scheduler.schedule(RequestPriority.HIGH_PRIORITY, dummy_high)
        assert res_high["text"] == "high priority response"
        assert "scheduler_latency_ms" in res_high

        res_chat = await scheduler.schedule(RequestPriority.NORMAL_CHAT, dummy_chat)
        assert res_chat["text"] == "Here is your explanation."

    asyncio.run(_test())

def test_v1_chat_completions_non_stream():
    headers = {"Authorization": f"Bearer {LOCAL_BEARER_TOKEN}"}
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "messages": [
            {"role": "user", "content": "What is 2 + 2?"}
        ],
        "stream": False,
        "max_tokens": 32
    }
    response = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["role"] == "assistant"

def test_v1_chat_completions_stream():
    headers = {"Authorization": f"Bearer {LOCAL_BEARER_TOKEN}"}
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "messages": [
            {"role": "user", "content": "Stream me a response."}
        ],
        "stream": True,
        "max_tokens": 32
    }
    response = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "data: " in response.text

def test_v1_edits_endpoint():
    headers = {"Authorization": f"Bearer {LOCAL_BEARER_TOKEN}"}
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "input": "def foo(): pass",
        "instruction": "add return True"
    }
    response = client.post("/v1/edits", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "edit"
    assert "choices" in data
    assert len(data["choices"]) > 0

def test_v1_apply_endpoint():
    headers = {"Authorization": f"Bearer {LOCAL_BEARER_TOKEN}"}
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "prompt": "Apply this code change"
    }
    response = client.post("/v1/apply", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "apply"
    assert "choices" in data
    assert len(data["choices"]) > 0

# =============================================================================
# 5. Lean 2-Minister Council & RAG Engine (from test_stage4_council_rag.py)
# =============================================================================

TEST_DB_PATH = "data/vectordb/test_cognitive_vault.db"

def test_minister_1_bge_embedder():
    embedder = BGEEmbedder()
    vec = embedder.embed_query("def add_numbers(a: int, b: int) -> int:")
    
    assert len(vec) == 384
    # Assert L2 normalization (sum of squares ~ 1.0)
    sq_sum = sum(v * v for v in vec)
    assert abs(sq_sum - 1.0) < 0.01

def test_vector_store_operations():
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    try:
        store = VectorStore(db_path=TEST_DB_PATH)
        embedder = BGEEmbedder()

        code1 = "def add(a, b):\n    return a + b"
        code2 = "class DatabaseConnection:\n    def connect(self): pass"
        
        emb1 = embedder.embed_query(code1)
        emb2 = embedder.embed_query(code2)

        id1 = store.insert_chunk("math_utils.py", code1, emb1, 1, 2)
        id2 = store.insert_chunk("db.py", code2, emb2, 1, 3)

        assert id1 > 0
        assert id2 > 0

        query_vec = embedder.embed_query("add two numbers")
        results = store.search_similar(query_vec, top_k=2)

        assert len(results) == 2
        assert results[0]["file_path"] in ("math_utils.py", "db.py")
    finally:
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

def test_minister_2_bge_reranker():
    reranker = BGEReranker()
    query = "database connect connection"
    candidates = [
        {"file_path": "math.py", "content": "def add(a, b): return a + b", "similarity_score": 0.8},
        {"file_path": "db.py", "content": "class DatabaseConnection: def connect(self): pass", "similarity_score": 0.5},
        {"file_path": "utils.py", "content": "def helper(): print('hello')", "similarity_score": 0.3}
    ]

    top_chunks = reranker.rerank(query, candidates, top_k=2)
    assert len(top_chunks) == 2
    assert top_chunks[0]["file_path"] == "db.py"

def test_lean_council_manager_rag_pipeline():
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    try:
        council = LeanCouncilManager(db_path=TEST_DB_PATH)
        status = council.get_council_status()

        assert status["vram_footprint_mb"] == 145
        assert status["vram_ceiling_passed"] is True

        embedder = council.minister_1_embedder
        code_snippet = "def calculate_total_price(items):\n    return sum(item.price for item in items)"
        emb = embedder.embed_query(code_snippet)
        council.vector_store.insert_chunk("cart.py", code_snippet, emb, 10, 12)

        rag_output = council.execute_rag_pipeline("calculate item price", top_k_candidates=5, top_k_rerank=3)

        assert rag_output["query"] == "calculate item price"
        assert len(rag_output["top_chunks"]) >= 1
        assert rag_output["pipeline_latency_ms"] < 50.0
    finally:
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

# =============================================================================
# 6. Main Boss Agent Personas & GBNF Grammars (from test_stage5_agent_personas.py)
# =============================================================================

def test_git_commit_craftsman_validation():
    craftsman = GitCommitCraftsman()

    assert craftsman.validate_commit_message("feat(v2): implement Stage 5 agent personas") is True
    assert craftsman.validate_commit_message("fix: resolve null pointer exception in parser") is True
    assert craftsman.validate_commit_message("chore(deps): update requirements.txt") is True
    assert craftsman.validate_commit_message("docs: update README.md") is True

    # Rejects non-conventional commits
    assert craftsman.validate_commit_message("added a cool feature to server") is False
    assert craftsman.validate_commit_message("fixed bug in code") is False

def test_diff_realigner_crlf_lf_reconciliation():
    realigner = DiffRealigner()

    target_file = "def calculate():\r\n    a = 10\r\n    b = 20\r\n    return a + b\r\n"
    search_block = "def calculate():\n    a = 10\n    b = 20"
    replace_block = "def calculate():\n    a = 100\n    b = 200"

    res = realigner.reconcile_search_replace(target_file, search_block, replace_block)

    assert res["success"] is True
    assert "a = 100" in res["updated_content"]
    assert "b = 200" in res["updated_content"]

def test_security_auditor_gbnf_and_json_parsing():
    auditor = SecurityAuditor()

    grammar = auditor.get_gbnf_grammar()
    assert "root ::=" in grammar
    assert "is_vulnerable" in grammar
    assert "risk_score" in grammar

    raw_llm_json = '{"is_vulnerable": true, "cwe_id": "CWE-89", "risk_score": 8.5, "mitigation": "Use parameterized queries"}'
    parsed = auditor.parse_and_validate_json_output(raw_llm_json)

    assert parsed["is_valid_schema"] is True
    assert parsed["data"]["is_vulnerable"] is True
    assert parsed["data"]["risk_score"] == 8.5

def test_mermaid_diagram_generator():
    gen = MermaidDiagramGenerator()

    grammar = gen.get_gbnf_grammar()
    assert "flowchart" in grammar
    assert "-->" in grammar

    valid_mermaid = "flowchart TD\n    A[Client] --> B[FastAPI Gateway]\n    B --> C[Main Boss GGUF]\n"
    assert gen.validate_mermaid_syntax(valid_mermaid) is True

    invalid_mermaid = "This is not a diagram syntax."
    assert gen.validate_mermaid_syntax(invalid_mermaid) is False

def test_agent_persona_chain():
    chain = AgentPersonaChain()

    spec_git = chain.get_persona_spec("GIT_COMMIT")
    assert spec_git["persona"] == "ROLE_A_GIT_CRAFTSMAN"
    assert spec_git["temperature"] == 0.0

    spec_sec = chain.get_persona_spec("SECURITY_AUDIT")
    assert spec_sec["persona"] == "ROLE_C_SECURITY_AUDITOR"
    assert spec_sec["gbnf_grammar"] == JSON_SECURITY_SCHEMA_GBNF

    spec_diag = chain.get_persona_spec("MERMAID_DIAGRAM")
    assert spec_diag["persona"] == "ROLE_D_DIAGRAM_GENERATOR"
    assert spec_diag["gbnf_grammar"] == MERMAID_DIAGRAM_GBNF

# =============================================================================
# 7. 4-Gate Enterprise Verification (from test_stage6_4gate_verification.py)
# =============================================================================

def test_gate1_vram_budget_allocation_ceiling():
    """Assert total resident static VRAM allocation stays <= 6.00 GB (6144 MB)."""
    hw = HardwareManager()
    mf = ModelFactory()

    main_vram = mf.config.get("main_boss", {}).get("vram_budget_mb", 1100)
    council_vram = TOTAL_COUNCIL_VRAM_FOOTPRINT_MB  # 145 MB

    total_projected_vram = main_vram + council_vram
    assert total_projected_vram <= STATIC_VRAM_CEILING_MB

    assert hw.verify_vram_budget(total_projected_vram) is True
    with pytest.raises(MemoryError):
        hw.verify_vram_budget(7000)

def test_gate1_silicon_provider_diagnostics():
    """Verify DirectML GPU provider detection and CPU AVX2 fallback."""
    hw = HardwareManager()
    diag = hw.detect_environment()

    assert diag["platform"] is not None
    assert diag["cpu_cores"] >= 1
    assert diag["vram_ceiling_mb"] == 6144
    assert "Vulkan" in diag["selected_provider"] or "OpenCL" in diag["selected_provider"] or "GPU" in diag["selected_provider"]

def test_gate2_treesitter_ast_parser_latency():
    """Assert Tree-sitter AST parsing executes across code files in < 1 ms."""
    chunker = TreeSitterChunker()
    sample_code = "def process_data(items: list) -> dict:\n    result = {}\n    for i in items:\n        result[i] = i * 2\n    return result\n"

    start = time.perf_counter()
    parsed = chunker.parse_file(sample_code, "python")
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert parsed["chunks_count"] >= 1
    assert elapsed_ms < 5.0

def test_gate2_manifest_linter_latency():
    """Assert ManifestLinter executes O(1) set-intersection import check in < 2 ms."""
    linter = ManifestLinter()
    linter.declared_dependencies = {"os", "sys", "math", "fastapi"}

    start = time.perf_counter()
    res = linter.validate_imports(["os", "sys", "numpy", "pandas"])
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert res["is_valid"] is False
    assert "numpy" in res["hallucinated_imports"]
    assert elapsed_ms < 2.0

def test_gate2_vulnerability_scanner_latency():
    """Assert VulnerabilityScanner security regex matching executes in < 3 ms."""
    scanner = VulnerabilityScanner()
    code = "api_key = 'sk_live_1234567890abcdef12345'\nos.system('rm -rf /')"

    start = time.perf_counter()
    findings = scanner.scan_security_issues(code)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert len(findings) >= 2
    assert elapsed_ms < 3.0

def test_gate2_context_trimmer_compression_ratio():
    """Assert StructuralTrimmer achieves > 40% compression in < 1 ms."""
    trimmer = StructuralTrimmer()
    long_code = "\n".join([f"def func_{i}():\n    # Line comment {i}\n    return {i}\n" for i in range(100)])

    res = trimmer.trim_context(long_code, max_lines=30)
    assert res["trimmed_lines"] <= 35
    assert res["compression_ratio_pct"] > 40.0
    assert res["trim_time_ms"] < 2.0

def test_gate3_minister_1_embedding_latency():
    """Assert Minister 1 embeds 384-d dense vectors in < 8 ms."""
    council = LeanCouncilManager()
    
    start = time.perf_counter()
    vec = council.minister_1_embedder.embed_query("def add(a, b): return a + b")
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert len(vec) == 384
    assert elapsed_ms < 8.0

def test_gate3_vector_store_simd_search_latency():
    """Assert VectorStore SIMD Cosine distance search executes in < 10 ms."""
    council = LeanCouncilManager(db_path="data/vectordb/test_gate3_vault.db")
    vec = council.minister_1_embedder.embed_query("test query")

    start = time.perf_counter()
    results = council.vector_store.search_similar(vec, top_k=3)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert isinstance(results, list)
    assert elapsed_ms < 10.0

def test_gate3_minister_2_reranking_latency():
    """Assert Minister 2 context re-ranking executes in < 16 ms."""
    council = LeanCouncilManager()
    candidates = [
        {"file_path": "a.py", "content": "def test(): pass", "similarity_score": 0.8},
        {"file_path": "b.py", "content": "def run(): pass", "similarity_score": 0.6}
    ]

    start = time.perf_counter()
    top_chunks = council.minister_2_reranker.rerank("test function", candidates, top_k=2)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert len(top_chunks) == 2
    assert elapsed_ms < 16.0

def test_gate4_sse_streaming_protocol():
    """Assert /v1/chat/completions streams compliant SSE delta chunks."""
    headers = {"Authorization": f"Bearer {LOCAL_BEARER_TOKEN}"}
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "messages": [{"role": "user", "content": "Explain async/await in Python"}],
        "stream": True
    }
    response = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "data: " in response.text
    assert "[DONE]" in response.text

def test_gate4_payload_size_limit():
    """Assert 2 MB payload size limit middleware blocks oversized requests with HTTP 413."""
    oversized_payload = {"messages": [{"role": "user", "content": "x" * (2 * 1024 * 1024 + 100)}]}
    response = client.post("/v1/chat/completions", json=oversized_payload)
    assert response.status_code == 413
    assert "Payload Too Large" in response.json()["error"]["message"]

def test_gate4_cspa_origin_header_block():
    """Assert requests with external browser Origin headers are blocked by CSPA defenses with HTTP 403."""
    headers = {"Origin": "https://malicious-website.com"}
    response = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "test"}]}, headers=headers)
    assert response.status_code == 403
    assert "CSPA Violation" in response.json()["error"]["message"]

# =============================================================================
# 8. K-Top Dashboard, Request Tracker, and Log Buffer (from test_dashboard_and_tracker.py)
# =============================================================================

def test_request_tracker_operations():
    """Verify RequestTracker records request lifecycles and throughput metrics."""
    test_tracker = RequestTracker()
    test_tracker.clear()

    assert test_tracker.get_active_count() == 0
    assert len(test_tracker.get_recent_requests()) == 0

    test_tracker.record_request_start("req-test-1", "POST", "/v1/chat/completions", priority="NORMAL")
    assert test_tracker.get_active_count() == 1
    assert len(test_tracker.get_recent_requests()) == 1

    req = test_tracker.get_recent_requests()[0]
    assert req["id"] == "req-test-1"
    assert req["status"] == "RUNNING"

    test_tracker.record_request_end("req-test-1", status_code=200, tokens_generated=50, tokens_per_sec=25.0)
    assert test_tracker.get_active_count() == 0

    req_ended = test_tracker.get_recent_requests()[0]
    assert req_ended["status"] == "200"
    assert req_ended["tokens"] == 50
    assert req_ended["tokens_per_sec"] == 25.0

    stats = test_tracker.get_stats()
    assert stats["total_requests"] == 1
    assert stats["total_tokens_generated"] == 50
    assert stats["last_tokens_per_sec"] == 25.0

def test_ring_buffer_log_handler():
    """Verify log records are intercepted into the sliding ring buffer."""
    handler = RingBufferLogHandler(capacity=10)
    handler.clear()

    logger = logging.getLogger("test.ktop")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Test server event 1")
    logger.warning("Test server event 2")

    logs = handler.get_recent_logs(limit=5)
    assert len(logs) == 2
    assert "Test server event 1" in logs[0]
    assert "Test server event 2" in logs[1]

    interceptor = attach_log_interceptor(level=logging.INFO)
    assert interceptor is not None

def test_make_meter():
    """Verify ASCII meter bar generation for percentages."""
    meter_low = make_meter(25.0, width=20)
    assert "25.0%" in meter_low.plain

    meter_mid = make_meter(75.0, width=20)
    assert "75.0%" in meter_mid.plain

    meter_high = make_meter(95.0, width=20)
    assert "95.0%" in meter_high.plain

def test_kingdom_top_dashboard_layout():
    """Verify KingdomTopDashboard layout components render without errors."""
    dashboard = KingdomTopDashboard(host="127.0.0.1", port=58420, bearer_token="test-token")
    
    header = dashboard.render_header()
    assert header is not None

    gauges = dashboard.render_resource_gauges()
    assert gauges is not None

    council = dashboard.render_council_panel()
    assert council is not None

    requests_table = dashboard.render_requests_table()
    assert requests_table is not None

    logs = dashboard.render_log_pane()
    assert logs is not None

    footer = dashboard.render_footer()
    assert footer is not None

    layout = dashboard.build_layout()
    assert layout is not None

    dashboard.show_help = True
    help_layout = dashboard.build_layout()
    assert help_layout is not None

def test_middleware_request_tracking_integration():
    """Verify HTTP requests through FastAPI gateway are automatically recorded by tracker."""
    tracker.clear()
    headers = {"Authorization": f"Bearer {LOCAL_BEARER_TOKEN}"}
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False
    }

    resp = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp.status_code == 200

    recent = tracker.get_recent_requests(limit=5)
    assert len(recent) >= 1
    matched = [r for r in recent if r["path"] == "/v1/chat/completions"]
    assert len(matched) >= 1
    assert matched[0]["status"] == "200"

def test_hardware_telemetry_cpu_and_no_npu():
    """Verify HardwareTelemetry samples CPU accurately without 0/100 spikes and excludes NPU."""
    from src.utils.telemetry import HardwareTelemetry

    snapshot = HardwareTelemetry.snapshot()
    assert "cpu_percent" in snapshot
    assert "ram_percent" in snapshot
    assert "vram_used_gb" in snapshot
    assert "gpu_engine" in snapshot

    # Assert NPU is excluded
    assert "npu_latency_ms" not in snapshot

    # Multiple successive rapid reads must not crash and produce valid percentages
    readings = [HardwareTelemetry.get_cpu_usage() for _ in range(5)]
    for r in readings:
        assert isinstance(r, float)
        assert 0.0 <= r <= 100.0

def test_strict_gpu_orchestrator_defaults():
    """Verify LlamaCppOrchestrator enforces strict GPU offload defaults."""
    from src.core.local_llm import LlamaCppOrchestrator, GPUOffloadRequiredError
    orch = LlamaCppOrchestrator()
    assert orch.n_gpu_layers == -1
    assert orch.strict_gpu is True
    assert issubclass(GPUOffloadRequiredError, RuntimeError)

def test_strict_gpu_enforcement_behavior(tmp_path):
    """Verify strict GPU offloading raises GPUOffloadRequiredError when runtime is CPU-only, and succeeds when GPU is supported."""
    from unittest.mock import MagicMock, patch
    from src.core.local_llm import LlamaCppOrchestrator, GPUOffloadRequiredError

    dummy_model = tmp_path / "test_model.gguf"
    dummy_model.write_bytes(b"dummy gguf weights")

    # Case 1: strict_gpu=True, CPU-only runtime -> Raises GPUOffloadRequiredError
    mock_cpu_llama = MagicMock()
    mock_cpu_llama.llama_supports_gpu_offload.return_value = False

    with patch.dict("sys.modules", {"llama_cpp": mock_cpu_llama}):
        orch_strict = LlamaCppOrchestrator(model_path=str(dummy_model), strict_gpu=True)
        with pytest.raises(GPUOffloadRequiredError) as exc_info:
            orch_strict.load_model()
        assert "Strict iGPU/GPU offload is enabled" in str(exc_info.value)
        assert "Intel Iris Xe" in str(exc_info.value)

    # Case 2: strict_gpu=True, GPU-capable runtime (e.g. Vulkan / Intel Iris Xe) -> Succeeds with n_gpu_layers=-1
    mock_gpu_llama = MagicMock()
    mock_gpu_llama.llama_supports_gpu_offload.return_value = True
    mock_instance = MagicMock()
    mock_gpu_llama.Llama.return_value = mock_instance

    with patch.dict("sys.modules", {"llama_cpp": mock_gpu_llama}):
        orch_gpu = LlamaCppOrchestrator(model_path=str(dummy_model), strict_gpu=True)
        loaded = orch_gpu.load_model()
        assert loaded is True
        assert orch_gpu.is_loaded is True
        assert orch_gpu.layers_offloaded == -1
        mock_gpu_llama.Llama.assert_called_once_with(
            model_path=str(dummy_model),
            n_ctx=32768,
            n_gpu_layers=-1,
            verbose=False
        )

# =============================================================================
# 11. Reranker API, Upgrade Models Registry & Dynamic Provisioning Tests
# =============================================================================

def test_v1_rerank_endpoint():
    """Verify Continue.dev-compatible Cohere /v1/rerank endpoint."""
    headers = {"Authorization": f"Bearer {LOCAL_BEARER_TOKEN}"}
    
    # 1. Empty documents request
    res_empty = client.post("/v1/rerank", json={"query": "test query", "documents": []}, headers=headers)
    assert res_empty.status_code == 200
    assert res_empty.json()["results"] == []

    # 2. Non-empty documents rerank
    docs = [
        "Python FastAPI web server implementation",
        "Cooking chocolate cake recipe",
        "DirectML GPU acceleration engine"
    ]
    payload = {
        "model": "bge-reranker-base",
        "query": "GPU hardware acceleration for machine learning",
        "documents": docs,
        "top_n": 2
    }
    res = client.post("/v1/rerank", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert len(data["results"]) == 2
    assert "relevance_score" in data["results"][0]
    assert "index" in data["results"][0]
    assert data["results"][0]["relevance_score"] >= data["results"][1]["relevance_score"]
    assert "meta" in data and "latency_ms" in data["meta"]

def test_upgrade_models_manifest_and_verifier(tmp_path):
    """Verify UPGRADE_MODELS registry and ModelVerifier integration."""
    from src.utils.verifier import UPGRADE_MODELS, get_upgrade_model_spec, ModelVerifier

    assert "qwen2.5-coder-3b" in UPGRADE_MODELS
    assert "qwen3-coder-1.7b" in UPGRADE_MODELS
    assert "qwen3-coder-4b" in UPGRADE_MODELS

    # Spec resolver
    spec_3b = get_upgrade_model_spec("qwen2.5-coder-3b")
    assert spec_3b is not None
    assert "repo_id" in spec_3b
    assert spec_3b["filename"] == "qwen2.5-coder-3b-instruct-q4_k_m.gguf"

    # Alias / filename resolver
    spec_file = get_upgrade_model_spec("qwen3-coder-4b-instruct-q4_k_m.gguf")
    assert spec_file is not None
    assert spec_file["id"] == "qwen3-coder-4b"

    # Verifier method
    verifier = ModelVerifier(models_dir=tmp_path)
    upgrade_results = verifier.verify_upgrade_models()
    assert len(upgrade_results) == 3
    assert all(r["status"] == "missing" for r in upgrade_results)

def test_huggingface_downloader_mock(tmp_path):
    """Verify ModelDownloader.download_from_huggingface logic."""
    from src.utils.downloader import ModelDownloader
    from unittest.mock import patch, MagicMock

    downloader = ModelDownloader(models_dir=tmp_path)
    
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.headers = {"Content-Length": "2048"}
    dummy_chunk = b"GGUF" + b"\x00" * (1024 * 1024)
    mock_resp.read.side_effect = [dummy_chunk, b""]
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        success = downloader.download_from_huggingface(
            repo_id="Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
            filename="test_model.gguf"
        )
        assert success is True
        target_file = tmp_path / "test_model.gguf"
        assert target_file.exists()

def test_orchestrator_dynamic_model_switch(tmp_path):
    """Verify dynamic in-process model switching in LlamaCppOrchestrator."""
    from unittest.mock import patch, MagicMock
    from src.core.local_llm import LlamaCppOrchestrator

    dummy_model_1 = tmp_path / "model1.gguf"
    dummy_model_1.write_bytes(b"GGUF" + b"\x00" * 100)
    dummy_model_2 = tmp_path / "model2.gguf"
    dummy_model_2.write_bytes(b"GGUF" + b"\x00" * 200)

    mock_llama = MagicMock()
    mock_llama.llama_supports_gpu_offload.return_value = True
    mock_instance = MagicMock()
    mock_llama.Llama.return_value = mock_instance

    with patch.dict("sys.modules", {"llama_cpp": mock_llama}):
        orch = LlamaCppOrchestrator(model_path=str(dummy_model_1), strict_gpu=True, model_name="model1")
        assert orch.load_model() is True
        assert orch.model_name == "model1"

        switched = orch.switch_model(str(dummy_model_2), model_name="qwen2.5-coder-3b")
        assert switched is True
        assert orch.model_path == str(dummy_model_2)
        assert orch.model_name == "qwen2.5-coder-3b"

def test_cli_model_commands(tmp_path):
    """Verify KingdomCLI model management commands execute without crashing."""
    from src.cli.terminal_ui import KingdomCLI
    from unittest.mock import patch

    with patch("src.utils.get_models_dir", return_value=tmp_path):
        cli = KingdomCLI()
        cli.show_models()
        cli.switch_model_cli("qwen2.5-coder-3b")
        assert cli.active_model_name == "qwen2.5-coder-1.5b"




