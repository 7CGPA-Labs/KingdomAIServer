"""
Integration tests for Headless OpenAI-compatible endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from src.inference.inference_engine import app

client = TestClient(app)

def test_payload_size_limit_middleware():
    """Test 2 MB payload size limit middleware."""
    large_payload = {"messages": [{"role": "user", "content": "x" * (2 * 1024 * 1024 + 100)}]}
    response = client.post("/v1/chat/completions", json=large_payload)
    assert response.status_code == 413
    assert "Payload Too Large" in response.json()["error"]["message"]

def test_workspace_path_jail():
    """Test WorkspacePathJail blocks traversal into sensitive user/system directories."""
    from src.core.ministers import WorkspacePathJail, WorkspacePathJailError
    with pytest.raises(WorkspacePathJailError):
        WorkspacePathJail.validate_path("C:\\Users\\test\\.ssh\\id_rsa")


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
