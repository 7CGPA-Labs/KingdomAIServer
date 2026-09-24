"""
Consolidated V2 Engine & Response Cache Test Suite.
Combines ResponseCacheDB, Startup Prefill Manager, Vector Vault Prefill,
LLM Warmup, and Chat Context Tool Enrichment.
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from src.processing.cache import ResponseCacheDB
from src.rag.vector_store import VectorStore
from src.rag.embedder import BGEEmbedder
from src.core.local_llm import LlamaCppOrchestrator
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
