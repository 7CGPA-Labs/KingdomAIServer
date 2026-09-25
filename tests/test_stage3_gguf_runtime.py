"""
Unit Tests & API Benchmarks for Stage 3: GGUF Runtime Core & Chat Completions Gateway.
Verifies:
- LlamaCppOrchestrator Fallback & ChatML Formatting
- PriorityInferenceScheduler Execution
- FastAPI /v1/chat/completions (Stream and Non-Stream) Endpoints
- FastAPI /v1/edits and /v1/apply Endpoints
"""
import asyncio
from fastapi.testclient import TestClient
from src.core.local_llm import LlamaCppOrchestrator
from src.inference.priority_queue import PriorityInferenceScheduler, RequestPriority
from src.inference.inference_engine import app, LOCAL_BEARER_TOKEN

client = TestClient(app)

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
