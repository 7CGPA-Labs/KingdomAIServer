"""
Cognitive Memory Vault using SQLite + sqlite-vec virtual tables (vec0).
"""
import sqlite3
from typing import List, Dict, Any
from pathlib import Path

class VectorStore:
    """Manages persistent sqlite-vec vector database for codebase chunks and memory vault."""

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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()

    def insert_chunk(self, file_path: str, content: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO memory_chunks (file_path, content) VALUES (?, ?)", (file_path, content))
        conn.commit()
        chunk_id = cursor.lastrowid
        conn.close()
        return chunk_id
