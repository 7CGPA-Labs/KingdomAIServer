"""
Comprehensive Unit & Integration Test Suite for Kingdom AI Studio V3.
Tests the Slint GUI Controller, Telemetry Bridge, Worker Threads, and Models Adapter.
"""
import time
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import slint

from src.gui.models_adapter import (
    STUDIO_MODELS_CATALOG,
    get_model_spec,
    get_model_filepath,
    build_slint_model_list
)
from src.gui.telemetry_bridge import TelemetryBridge
from src.gui.worker import InferenceWorker, DownloadWorker
from src.gui.app_controller import AppController
from src.processing.cache import ResponseCacheDB


# =============================================================================
# 1. Models Adapter Tests
# =============================================================================

def test_models_adapter_catalog_and_specs():
    """Verify models adapter catalog contains all expected models and aliases."""
    assert "qwen2.5-coder-1.5b" in STUDIO_MODELS_CATALOG
    assert "qwen2.5-coder-3b" in STUDIO_MODELS_CATALOG
    assert "qwen3-coder-1.7b" in STUDIO_MODELS_CATALOG
    assert "qwen3-coder-4b" in STUDIO_MODELS_CATALOG
    assert "deepseek-coder-1.3b" in STUDIO_MODELS_CATALOG

    spec = get_model_spec("qwen2.5-coder-1.5b")
    assert spec is not None
    assert spec["name"] == "Qwen 2.5 Coder 1.5B"
    assert "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf" in spec["filename"]

    # Case-insensitive resolution
    spec_upper = get_model_spec("QWEN 2.5 CODER 3B")
    assert spec_upper is not None
    assert spec_upper["id"] == "qwen2.5-coder-3b"


def test_build_slint_model_list(tmp_path):
    """Verify build_slint_model_list correctly marks active and installed models."""
    # Create fake model file
    fake_model = tmp_path / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    fake_model.write_bytes(b"\x00" * (12 * 1024 * 1024))  # 12 MB

    model_list = build_slint_model_list("qwen2.5-coder-1.5b", models_dir=tmp_path)
    assert isinstance(model_list, slint.ListModel)
    assert len(model_list) == len(STUDIO_MODELS_CATALOG)

    first = model_list[0]
    assert first["id"] == "qwen2.5-coder-1.5b"
    assert first["is_active"] is True
    assert first["is_installed"] is True
    assert first["actual_disk_mb"] >= 12.0

    second = model_list[1]
    assert second["is_active"] is False
    assert second["is_installed"] is False


# =============================================================================
# 2. Telemetry Bridge Tests
# =============================================================================

def test_telemetry_bridge_updates(tmp_path):
    """Verify TelemetryBridge samples hardware and applies values to Slint window."""
    app_path = Path(__file__).resolve().parent.parent / "ui" / "app.slint"
    ns = slint.load_file(str(app_path))
    window = ns.MainWindow()

    db_path = tmp_path / "test_cache.db"
    cache = ResponseCacheDB(db_path=db_path)
    cache.put("key1", "resp1", {"text": "resp1"})

    bridge = TelemetryBridge(window, cache_db=cache)
    bridge.update_once()

    # Hardware properties must be populated with realistic non-negative values
    assert window.cpu_pct >= 0.0
    assert window.ram_used_gb > 0.0
    assert window.ram_total_gb > 0.0
    assert window.vram_used_gb >= 0.0
    assert window.vram_ceiling_gb == 6.0
    assert "GB" in window.vram_status
    assert window.cache_entries == 1


# =============================================================================
# 3. Inference Worker Tests
# =============================================================================

def test_inference_worker_streaming():
    """Verify InferenceWorker streams tokens and triggers completion callback."""
    mock_orch = MagicMock()
    mock_orch.model_name = "qwen2.5-coder-1.5b"
    mock_orch.stream_chat_completion.return_value = [
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [{"delta": {"content": " "}}]},
        {"choices": [{"delta": {"content": "World!"}}]}
    ]

    tokens_received = []
    completion_data = {}

    def on_token(delta, accum):
        tokens_received.append(delta)

    def on_complete(text, tps, latency):
        completion_data["text"] = text
        completion_data["tps"] = tps
        completion_data["latency"] = latency

    worker = InferenceWorker(
        orchestrator=mock_orch,
        messages=[{"role": "user", "content": "Hi"}],
        on_token=on_token,
        on_complete=on_complete,
        on_error=lambda err: None
    )

    worker.start()
    worker._thread.join(timeout=2.0)

    assert "".join(tokens_received) == "Hello World!"
    assert completion_data.get("text") == "Hello World!"
    assert completion_data.get("latency", 0) >= 0


def test_inference_worker_cancellation():
    """Verify InferenceWorker respects cancellation request."""
    def infinite_stream(*args, **kwargs):
        while True:
            yield {"choices": [{"delta": {"content": "loop"}}]}
            time.sleep(0.01)

    mock_orch = MagicMock()
    mock_orch.stream_chat_completion.side_effect = infinite_stream

    tokens = []
    worker = InferenceWorker(
        orchestrator=mock_orch,
        messages=[{"role": "user", "content": "Hi"}],
        on_token=lambda d, a: tokens.append(d),
        on_complete=lambda t, s, l: None,
        on_error=lambda e: None
    )

    worker.start()
    time.sleep(0.05)
    worker.cancel()
    worker._thread.join(timeout=1.0)

    assert not worker._thread.is_alive()


def test_inference_worker_instant_cache_hit(tmp_path):
    """Verify InferenceWorker yields instant cached response without invoking LLM."""
    db_path = tmp_path / "cache.db"
    cache = ResponseCacheDB(db_path=db_path)

    cache_key = cache.compute_cache_key("qwen2.5-coder-1.5b", "Fast Query", max_tokens=1024, temperature=0.7)
    cache.put(cache_key, "Cached Output Answer", {"text": "Cached Output Answer"})

    mock_orch = MagicMock()
    mock_orch.model_name = "qwen2.5-coder-1.5b"

    result = {}
    worker = InferenceWorker(
        orchestrator=mock_orch,
        messages=[{"role": "user", "content": "Fast Query"}],
        on_token=lambda d, a: None,
        on_complete=lambda t, s, l: result.update({"text": t, "tps": s, "latency": l}),
        on_error=lambda e: None,
        cache_db=cache
    )

    worker.start()
    worker._thread.join(timeout=2.0)

    assert result["text"] == "Cached Output Answer"
    assert result["tps"] == 999.0  # Instant hit marker
    # The LLM stream must never have been called
    mock_orch.stream_chat_completion.assert_not_called()


# =============================================================================
# 4. AppController & Slash Commands Integration Tests
# =============================================================================

def test_app_controller_initialization():
    """Verify AppController initializes MainWindow with default models and messages."""
    ctrl = AppController(auto_start_telemetry=False)
    assert ctrl.window is not None
    assert ctrl.window.active_nav == "chat"
    assert ctrl.window.active_model == "Qwen 2.5 Coder 1.5B"
    assert len(ctrl.window.model_list) == len(STUDIO_MODELS_CATALOG)
    assert len(ctrl.window.chat_messages) == 1
    assert "Welcome to Kingdom AI Studio" in ctrl.window.chat_messages[0]["content"]


def test_app_controller_slash_commands(tmp_path):
    """Verify slash command routing (/top, /models, /health, /help, /cache, /clear)."""
    db_path = tmp_path / "test_cache.db"
    cache = ResponseCacheDB(db_path=db_path)
    ctrl = AppController(cache_db=cache, auto_start_telemetry=False)

    # 1. /top
    ctrl.on_execute_command("/top")
    assert ctrl.window.active_nav == "ktop"

    # 2. /models
    ctrl.on_execute_command("/models")
    assert ctrl.window.active_nav == "models"

    # 3. /health
    initial_count = len(ctrl.window.chat_messages)
    ctrl.on_execute_command("/health")
    assert len(ctrl.window.chat_messages) == initial_count + 1
    assert "Diagnostics" in ctrl.window.chat_messages[-1]["content"]

    # 4. /help
    ctrl.on_execute_command("/help")
    assert "Available Slash Commands" in ctrl.window.chat_messages[-1]["content"]

    # 5. /cache
    ctrl.on_execute_command("/cache")
    assert "Response Cache DB" in ctrl.window.chat_messages[-1]["content"]

    # 6. /clear
    ctrl.on_execute_command("/clear")
    assert len(ctrl.window.chat_messages) == 0

    # 7. /newchat via on_new_chat
    ctrl.on_new_chat()
    assert len(ctrl.window.chat_messages) == 1


def test_app_controller_purge_cache(tmp_path):
    """Verify cache purging updates UI metrics."""
    db_path = tmp_path / "test_cache.db"
    cache = ResponseCacheDB(db_path=db_path)
    cache.put("k1", "v1", {"text": "v1"})
    assert cache.get_stats()["total_cached_entries"] == 1

    ctrl = AppController(cache_db=cache, auto_start_telemetry=False)
    ctrl.on_purge_cache()

    assert cache.get_stats()["total_cached_entries"] == 0
    assert ctrl.window.cache_entries == 0
    assert ctrl.window.cache_hits == 0


def test_download_worker_already_installed(tmp_path):
    """Verify DownloadWorker short-circuits when model is already present."""
    fake_model = tmp_path / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    fake_model.write_bytes(b"\x00" * (1200 * 1024 * 1024))

    progresses = []
    completed = []

    worker = DownloadWorker(
        model_id="qwen2.5-coder-1.5b",
        on_progress=lambda p, s: progresses.append((p, s)),
        on_complete=lambda ok, msg: completed.append((ok, msg)),
        models_dir=tmp_path
    )
    worker.start()
    worker._thread.join(timeout=2.0)

    assert len(completed) == 1
    assert completed[0][0] is True
    assert "already installed" in completed[0][1]
