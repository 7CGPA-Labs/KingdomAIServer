"""
Prefill & Warmup Manager for Kingdom AI Server V2.
Prefills SQLite Response Cache DB, Cognitive Vector Vault, and KV Cache on startup.
Eliminates cold-start latency and arms the server with instant standard library and template hits.
"""
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.processing.cache import ResponseCacheDB
from src.rag.vector_store import VectorStore
from src.rag.embedder import BGEEmbedder
from src.core.local_llm import LlamaCppOrchestrator

# Standard common developer interactions and greetings to prefill in Response Cache DB
SEED_CHAT_INTERACTIONS = [
    ("hi", "Hello! I am Main Boss, the lead AI developer in Kingdom AI Server V2. How can I assist you with your code today?"),
    ("hello", "Hello! I am ready to help you write, refactor, and review code. What are we working on?"),
    ("who are you", "I am Main Boss, an enterprise-secure, local AI developer engine running on Kingdom AI Server V2."),
    ("what can you do", "I provide code generation, refactoring, security auditing, RAG codebase search, and Mermaid diagram generation."),
    ("help", "You can ask me to explain code, fix bugs, generate tests, refactor functions, or search across your indexed repository."),
    ("how to reverse a string in python", "In Python, you can reverse a string using slicing: `reversed_str = original_str[::-1]`."),
    ("python fibonacci", "Here is an efficient Fibonacci function in Python:\n\ndef fibonacci(n: int) -> int:\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a"),
    ("fastapi health check", "Here is a standard FastAPI health check endpoint:\n\n@app.get('/health')\nasync def health():\n    return {'status': 'ok'}"),
    ("git commit convention", "Conventional Commits follow the format: `type(scope): description`. Common types include feat, fix, docs, style, refactor, test, and chore."),
    ("dockerfile python", "Here is a clean Python Dockerfile template:\n\nFROM python:3.11-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nCMD [\"python\", \"main.py\"]")
]

# Standard architectural templates to prefill in Vector DB
SEED_TEMPLATES = [
    {
        "file_path": "templates/java/CustomHealthIndicator.java",
        "content": (
            "package com.example.employee.customHealth;\n\n"
            "import org.springframework.boot.actuate.health.Health;\n"
            "import org.springframework.boot.actuate.health.HealthIndicator;\n"
            "import org.springframework.stereotype.Component;\n\n"
            "@Component\n"
            "public class CustomHealthIndicator implements HealthIndicator {\n"
            "    @Override\n"
            "    public Health health() {\n"
            "        // Poll database connectivity and health\n"
            "        boolean isDatabaseHealthy = checkDatabase();\n"
            "        if (isDatabaseHealthy) {\n"
            "            return Health.up().withDetail(\"database\", \"Operational\").build();\n"
            "        }\n"
            "        return Health.down().withDetail(\"database\", \"Unreachable\").build();\n"
            "    }\n"
            "    private boolean checkDatabase() { return true; }\n"
            "}"
        )
    },
    {
        "file_path": "templates/java/EmployeeRepository.java",
        "content": (
            "package com.example.employee.repository;\n\n"
            "import org.springframework.data.jpa.repository.JpaRepository;\n"
            "import org.springframework.stereotype.Repository;\n"
            "import java.util.Optional;\n\n"
            "@Repository\n"
            "public interface EmployeeRepository extends JpaRepository<Employee, Long> {\n"
            "    Optional<Employee> findByEmail(String email);\n"
            "    boolean existsByEmail(String email);\n"
            "}"
        )
    },
    {
        "file_path": "templates/python/FastAPIService.py",
        "content": (
            "from fastapi import FastAPI, Depends, HTTPException, status\n"
            "from pydantic import BaseModel\n\n"
            "app = FastAPI(title='Microservice API')\n\n"
            "@app.get('/health')\n"
            "async def health_check():\n"
            "    return {'status': 'healthy', 'timestamp': time.time()}\n"
        )
    },
    {
        "file_path": "templates/typescript/fetchWithAbort.ts",
        "content": (
            "export async function fetchWithAbort<T>(url: string, signal?: AbortSignal): Promise<T> {\n"
            "    const response = await fetch(url, { signal });\n"
            "    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);\n"
            "    return response.json() as Promise<T>;\n"
            "}"
        )
    }
]

def prefill_response_cache(cache_db: ResponseCacheDB, model_name: str = "qwen2.5-coder-1.5b") -> int:
    """Populate ResponseCacheDB with common developer interactions and greetings."""
    count = 0
    created_time = int(time.time())

    for prompt_text, reply in SEED_CHAT_INTERACTIONS:
        msgs = [{"role": "user", "content": prompt_text}]
        chat_key = ResponseCacheDB.compute_cache_key(model_name, json.dumps(msgs), "", temperature=0.7, max_tokens=8192)
        chat_data = {
            "id": f"chatcmpl-prefill-{count}",
            "object": "chat.completion",
            "created": created_time,
            "model": model_name,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 25}
        }
        cache_db.put(chat_key, reply, chat_data, query_type="CHAT")
        count += 1

    return count

def prefill_vector_store(vector_store: VectorStore, embedder: Optional[BGEEmbedder] = None) -> int:
    """Prefill Cognitive Vector Vault with standard architecture and language templates."""
    existing_chunks = vector_store.get_all_chunks()
    if len(existing_chunks) >= len(SEED_TEMPLATES):
        return len(existing_chunks)

    if embedder is None:
        embedder = BGEEmbedder()

    count = 0
    for tpl in SEED_TEMPLATES:
        vec = embedder.embed_query(tpl["content"])
        vector_store.insert_chunk(
            file_path=tpl["file_path"],
            content=tpl["content"],
            embedding=vec,
            line_start=1,
            line_end=len(tpl["content"].splitlines())
        )
        count += 1

    return count

def warmup_llm_engine(orchestrator: LlamaCppOrchestrator) -> bool:
    """Preload model weights into memory and warmup GPU tensors with a 1-token prefill."""
    try:
        if not orchestrator.is_loaded:
            orchestrator.load_model()
        # Warmup forward-pass through engine
        orchestrator.generate_completion("Warmup", max_tokens=1)
        return True
    except Exception:
        return False
