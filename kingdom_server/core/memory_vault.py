"""
Cognitive Memory & Persistence Backbone using SQLite + sqlite-vec (Repository Pattern).
Supports WAL mode, parameterized queries, short-term session history, and 384-dim vector semantic search.
"""
import sqlite3
import json
import time
import math
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from kingdom_server.utils import get_db_path

class MemoryVault:
    """Repository Pattern implementation for SQLite vector memory persistence."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else get_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.has_sqlite_vec = False
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        
        # Try loading sqlite-vec extension if present
        if not self.has_sqlite_vec:
            try:
                import sqlite_vec
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                self.has_sqlite_vec = True
            except Exception:
                self.has_sqlite_vec = False
        elif self.has_sqlite_vec:
            try:
                import sqlite_vec
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
            except Exception:
                pass
        return conn

    def _init_db(self):
        conn = self._get_connection()
        try:
            with conn:
                # Short-term chat session history
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS session_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp REAL NOT NULL
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON session_history(session_id);")

                # Long-term semantic & episodic vector store
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cognitive_vectors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        vector_blob BLOB NOT NULL,
                        timestamp REAL NOT NULL
                    );
                """)

                if self.has_sqlite_vec:
                    conn.execute("""
                        CREATE VIRTUAL TABLE IF NOT EXISTS vec_cognitive USING vec0(
                            embedding float[384]
                        );
                    """)
        finally:
            conn.close()

    def add_session_message(self, session_id: str, role: str, content: str):
        """Adds a message turn to short-term session history using parameterized query."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO session_history (session_id, role, content, timestamp) VALUES (?, ?, ?, ?);",
                    (session_id, role, content, time.time())
                )
        finally:
            conn.close()

    def get_session_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves recent session history turns."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT role, content, timestamp FROM session_history WHERE session_id = ? ORDER BY id DESC LIMIT ?;",
                (session_id, limit)
            )
            rows = cursor.fetchall()
            history = [{"role": row["role"], "content": row["content"], "timestamp": row["timestamp"]} for row in rows]
            history.reverse()
            return history
        finally:
            conn.close()

    def insert_vector(self, document: str, vector: List[float], metadata: Optional[dict] = None) -> int:
        """Inserts a 384-dim vector and document into cognitive memory."""
        conn = self._get_connection()
        try:
            meta_json = json.dumps(metadata or {})
            vector_blob = json.dumps(vector).encode("utf-8")
            with conn:
                cursor = conn.execute(
                    "INSERT INTO cognitive_vectors (document, metadata, vector_blob, timestamp) VALUES (?, ?, ?, ?);",
                    (document, meta_json, vector_blob, time.time())
                )
                doc_id = cursor.lastrowid
                
                if self.has_sqlite_vec and doc_id:
                    conn.execute(
                        "INSERT INTO vec_cognitive (rowid, embedding) VALUES (?, ?);",
                        (doc_id, json.dumps(vector))
                    )
                return doc_id or 0
        finally:
            conn.close()

    def search_similar(self, query_vector: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """Hybrid vector cosine distance similarity search (top k)."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT id, document, metadata, vector_blob FROM cognitive_vectors;")
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                doc_vector = json.loads(row["vector_blob"].decode("utf-8"))
                score = self._cosine_similarity(query_vector, doc_vector)
                meta = json.loads(row["metadata"]) if row["metadata"] else {}
                results.append({
                    "id": row["id"],
                    "document": row["document"],
                    "metadata": meta,
                    "score": round(score, 4),
                })

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:k]
        finally:
            conn.close()

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        if len(vec_a) != len(vec_b) or not vec_a:
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def get_stats(self) -> Dict[str, Any]:
        """Returns cognitive vector store statistics."""
        conn = self._get_connection()
        try:
            cur1 = conn.execute("SELECT COUNT(*) FROM session_history;")
            total_history = cur1.fetchone()[0]
            cur2 = conn.execute("SELECT COUNT(*) FROM cognitive_vectors;")
            total_vectors = cur2.fetchone()[0]
            return {
                "total_history_turns": total_history,
                "total_vectors_indexed": total_vectors,
                "sqlite_vec_enabled": self.has_sqlite_vec,
                "db_file": str(self.db_path),
            }
        finally:
            conn.close()

    def clear(self):
        """Clears all session history and vector store memory."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM session_history;")
                conn.execute("DELETE FROM cognitive_vectors;")
                if self.has_sqlite_vec:
                    conn.execute("DELETE FROM vec_cognitive;")
        finally:
            conn.close()
