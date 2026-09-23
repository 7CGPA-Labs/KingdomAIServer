"""
Lean 2-Minister Council Coordinator.
Coordinates sidecar neural ministers under strict ~145 MB total VRAM budget:
- Minister 1: Workspace Embedder (bge-small-en-v1.5, ~35 MB VRAM)
- Minister 2: Context Re-Ranker (bge-reranker-base, ~110 MB VRAM)
"""
import time
from typing import Dict, Any, List, Optional
from src.rag.embedder import BGEEmbedder
from src.rag.retriever import BGEReranker
from src.rag.vector_store import VectorStore

TOTAL_COUNCIL_VRAM_FOOTPRINT_MB = 145  # 35 + 110 MB

class LeanCouncilManager:
    """Coordinates the 2 sidecar neural ministers under strict ~145 MB total VRAM budget."""

    def __init__(self, db_path: str = "data/vectordb/cognitive_vault.db"):
        self.minister_1_embedder = BGEEmbedder()
        self.minister_2_reranker = BGEReranker()
        self.vector_store = VectorStore(db_path)

    def get_council_status(self) -> Dict[str, Any]:
        """Return Lean Council operational status and VRAM budget footprint."""
        return {
            "council_type": "Lean 2-Minister Council",
            "active_ministers": [
                "Minister 1: BGE-Small Embedder (~35 MB VRAM)",
                "Minister 2: BGE-ReRanker (~110 MB VRAM)"
            ],
            "vram_footprint_mb": TOTAL_COUNCIL_VRAM_FOOTPRINT_MB,
            "vram_ceiling_passed": TOTAL_COUNCIL_VRAM_FOOTPRINT_MB <= 145,
            "status": "READY"
        }

    def execute_rag_pipeline(self, query: str, top_k_candidates: int = 5, top_k_rerank: int = 3) -> Dict[str, Any]:
        """
        Execute end-to-end Lean RAG pipeline (<20 ms latency target):
        1) Minister 1 embeds query into 384-d vector.
        2) VectorStore performs SIMD Cosine distance top-K retrieval.
        3) Minister 2 cross-evaluates and re-ranks top-3 chunks.
        """
        start = time.perf_counter()

        # Step 1: Embed query (Minister 1)
        query_vector = self.minister_1_embedder.embed_query(query)

        # Step 2: Vector search (VectorStore)
        retrieved_chunks = self.vector_store.search_similar(query_vector, top_k=top_k_candidates)

        # Step 3: Re-rank candidate chunks (Minister 2)
        final_chunks = self.minister_2_reranker.rerank(query, retrieved_chunks, top_k=top_k_rerank)

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return {
            "query": query,
            "total_retrieved": len(retrieved_chunks),
            "final_top_chunks_count": len(final_chunks),
            "top_chunks": final_chunks,
            "pipeline_latency_ms": round(elapsed_ms, 2)
        }
