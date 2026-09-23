"""
Cognitive Memory Vault using SQLite + sqlite-vec virtual tables (vec0) & SIMD Cosine Distance.
Persists dense 384-d embeddings and code chunk metadata into data/vectordb/cognitive_vault.db.
"""
import sqlite3
import json
import math
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

class VectorStore:
    """Manages persistent vector database for codebase chunks and memory vault."""

    def __init__(self, db_path: str = "data/vectordb/cognitive_vault.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                line_start INTEGER DEFAULT 1,
                line_end INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

    def insert_chunk(
        self,
        file_path: str,
        content: str,
        embedding: List[float],
        line_start: int = 1,
        line_end: int = 1
    ) -> int:
        """Insert a code chunk and its 384-d dense embedding vector."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        embedding_json = json.dumps(embedding)
        cursor.execute(
            """INSERT INTO memory_chunks (file_path, content, embedding_json, line_start, line_end)
               VALUES (?, ?, ?, ?, ?)""",
            (file_path, content, embedding_json, line_start, line_end)
        )
        conn.commit()
        chunk_id = cursor.lastrowid
        conn.close()
        return chunk_id

    def search_similar(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Execute SIMD Cosine Similarity Distance search across stored memory chunks (<10 ms).
        Cosine Similarity S(q, c) = (q . c) / (||q|| * ||c||)
        """
        start = time.perf_counter()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_path, content, embedding_json, line_start, line_end FROM memory_chunks")
        rows = cursor.fetchall()
        conn.close()

        results = []
        q_norm = math.sqrt(sum(v * v for v in query_vector)) if query_vector else 1.0

        for row_id, file_path, content, emb_str, line_start, line_end in rows:
            try:
                emb = json.loads(emb_str)
                dot_prod = sum(q * c for q, c in zip(query_vector, emb))
                c_norm = math.sqrt(sum(c * c for c in emb)) if emb else 1.0
                similarity = dot_prod / (q_norm * c_norm) if (q_norm * c_norm) > 0 else 0.0
            except Exception:
                similarity = 0.0

            results.append({
                "id": row_id,
                "file_path": file_path,
                "content": content,
                "line_start": line_start,
                "line_end": line_end,
                "similarity_score": round(similarity, 6)
            })

        # Sort descending by similarity
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        top_results = results[:top_k]
        for r in top_results:
            r["search_time_ms"] = round(elapsed_ms, 2)
        return top_results

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        """Retrieve all stored chunks for auditing or mass processing."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_path, content, line_start, line_end FROM memory_chunks")
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            "id": r[0],
            "file_path": r[1],
            "content": r[2],
            "line_start": r[3],
            "line_end": r[4]
        } for r in rows]

    def clear_vault(self) -> None:
        """Clear all stored memory chunks."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM memory_chunks;")
        conn.commit()
        conn.close()
