"""
Unit Tests & API Benchmarks for Stage 3: GGUF Runtime Core & Main Boss FIM Autocomplete.
Verifies:
- FIM Sentinel Token Formatting
- LlamaCppOrchestrator Fallback & ChatML Formatting
- PriorityInferenceScheduler Dual Queue Execution
- FastAPI /v1/completions (FIM) and /v1/chat/completions Endpoints
"""
import pytest
import json
from fastapi.testclient import TestClient
from src.processing.tokenizer import FIMFormatter, format_fim_prompt, FIM_STOP_TOKENS
from src.core.local_llm import LlamaCppOrchestrator
from src.inference.priority_queue import PriorityInferenceScheduler, RequestPriority
from src.inference.inference_engine import app, LOCAL_BEARER_TOKEN

client = TestClient(app)

def test_fim_tokenizer_formatting():
    prefix = "def calculate_sum(a, b):\n    "
    suffix = "\n    return result"
    formatted = format_fim_prompt(prefix, suffix)

    assert "<|fim_prefix|>" in formatted
    assert "<|fim_suffix|>" in formatted
    assert "<|fim_middle|>" in formatted
    assert formatted.startswith("<|fim_prefix|>")

    params = FIMFormatter.get_sampling_params(max_tokens=32)
    assert params["temperature"] == 0.0
    assert "\n" in params["stop"]

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

    fim_res = orch.generate_fim_completion("def test():", "")
    assert fim_res["is_fim"] is True

import asyncio

def test_priority_scheduler():
    async def _test():
        scheduler = PriorityInferenceScheduler()
        
        def dummy_fim():
            return {"text": "return 42"}

        def dummy_chat():
            return {"text": "Here is your explanation."}

        res_fim = await scheduler.schedule(RequestPriority.HIGH_FIM, dummy_fim)
        assert res_fim["text"] == "return 42"
        assert "scheduler_latency_ms" in res_fim

        res_chat = await scheduler.schedule(RequestPriority.NORMAL_CHAT, dummy_chat)
        assert res_chat["text"] == "Here is your explanation."

    asyncio.run(_test())

def test_v1_completions_api_endpoint():
    headers = {"Authorization": f"Bearer {LOCAL_BEARER_TOKEN}"}
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "prefix": "def add(a, b):\n    ",
        "suffix": "\n",
        "max_tokens": 16,
        "temperature": 0.0
    }
    response = client.post("/v1/completions", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "text_completion"
    assert "choices" in data
    assert len(data["choices"]) > 0

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
