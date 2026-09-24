"""
Unit Tests for Prefill & Warmup Manager.
Verifies prefilling of ResponseCacheDB, Cognitive VectorStore, and LLM Tensor Warmup.
"""
import pytest
from src.processing.cache import ResponseCacheDB
from src.rag.vector_store import VectorStore
from src.rag.embedder import BGEEmbedder
from src.core.local_llm import LlamaCppOrchestrator
from src.processing.prefill import prefill_response_cache, prefill_vector_store, warmup_llm_engine

def test_prefill_response_cache(tmp_path):
    cache_path = tmp_path / "test_cache.db"
    db = ResponseCacheDB(db_path=cache_path)
    
    count = prefill_response_cache(db)
    assert count >= 10
    
    stats = db.get_stats()
    assert stats["total_cached_entries"] >= 10

def test_prefill_vector_store(tmp_path):
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
    orch = LlamaCppOrchestrator()
    # Should not throw any unhandled exceptions
    result = warmup_llm_engine(orch)
    assert isinstance(result, bool)
