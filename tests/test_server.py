"""
Integration tests for FastAPI OpenAI-compatible endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from kingdom_server.server.app import app

client = TestClient(app)

def test_health_endpoint():
    """Test /health endpoint returns active status and telemetry dictionary."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert data["version"] == "1.0.0"
    assert "telemetry" in data
    assert "silicon_tiers" in data
    assert "models" in data

def test_payload_size_limit_middleware():
    """Test 2 MB payload size limit middleware."""
    large_payload = {"messages": [{"role": "user", "content": "x" * (2 * 1024 * 1024 + 100)}]}
    response = client.post("/v1/chat/completions", json=large_payload)
    assert response.status_code == 413
    assert "Payload Too Large" in response.json()["error"]["message"]

def test_workspace_path_jail():
    """Test WorkspacePathJail blocks traversal into sensitive user/system directories."""
    from kingdom_server.core.ministers import WorkspacePathJail, WorkspacePathJailError
    with pytest.raises(WorkspacePathJailError):
        WorkspacePathJail.validate_path("C:\\Users\\test\\.ssh\\id_rsa")

def test_fast_completions_endpoint():
    """Test /v1/completions tab autocomplete endpoint."""
    payload = {
        "model": "granite-code-128m",
        "prefix": "def ",
        "suffix": "",
        "max_tokens": 16
    }
    response = client.post("/v1/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "text_completion"
    assert len(data["choices"]) > 0
    assert isinstance(data["choices"][0]["text"], str) and len(data["choices"][0]["text"]) > 0
    assert "latency_ms" in data
    assert data["latency_ms"] < 1000.0  # Must be fast sub-30ms execution

def test_embeddings_endpoint():
    """Test /v1/embeddings 384-dim vector generation endpoint."""
    payload = {
        "model": "bge-small-en-v1.5",
        "input": "def calculate_total(items): return sum(items)"
    }
    response = client.post("/v1/embeddings", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 1
    embedding = data["data"][0]["embedding"]
    assert len(embedding) == 384
    assert isinstance(embedding[0], float)

def test_chat_completions_non_stream_endpoint():
    """Test /v1/chat/completions non-stream JSON response."""
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "messages": [
            {"role": "user", "content": "Write a Python function to sort a list of numbers."}
        ],
        "stream": False
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) > 0
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert len(data["choices"][0]["message"]["content"]) > 0

def test_chat_completions_stream_endpoint():
    """Test /v1/chat/completions SSE streaming response."""
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "messages": [
            {"role": "user", "content": "Explain how async functions work in Python."}
        ],
        "stream": True
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    lines = response.text.split("\n")
    assert any(line.startswith("data: ") for line in lines)
    assert any("[DONE]" in line for line in lines)
