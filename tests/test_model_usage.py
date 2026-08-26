"""
Test suite to explicitly verify model loading and whether model sessions (GGUF / ONNX) are being used or operating in fallback mode.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from kingdom_server.core.hardware import HardwareAccelerationEngine
from kingdom_server.core.ministers import MinisterFactory, BaseMinister
from kingdom_server.core.orchestrator import KingdomOrchestrator

def test_ministers_onnx_loaded_property(tmp_path):
    """Verify is_onnx_loaded reports False when model files are missing and True when loaded."""
    hw_engine = HardwareAccelerationEngine()
    factory = MinisterFactory(hw_engine, models_dir=tmp_path)
    ministers = factory.create_all_ministers()

    for key, minister in ministers.items():
        assert minister.is_onnx_loaded is False, f"{minister.name} should report is_onnx_loaded=False when file missing"

def test_ministers_mock_onnx_session(tmp_path):
    """Verify that when ONNX session is active, is_onnx_loaded reports True."""
    hw_engine = HardwareAccelerationEngine()
    
    # Create a dummy model file
    dummy_model_file = tmp_path / "all-MiniLM-L6-v2.onnx"
    dummy_model_file.write_bytes(b"dummy onnx bytes")

    mock_ort = MagicMock()
    mock_session_cls = MagicMock()
    mock_instance = MagicMock()
    mock_session_cls.return_value = mock_instance
    mock_ort.InferenceSession = mock_session_cls

    with patch.dict("sys.modules", {"onnxruntime": mock_ort}):
        minister1 = MinisterFactory(hw_engine, models_dir=tmp_path).create_all_ministers()["minister_1"]
        assert minister1.is_onnx_loaded is True
        assert minister1.session == mock_instance

def test_orchestrator_boss_model_usage(tmp_path):
    """Verify orchestrator tracks whether Main Boss Qwen2.5 GGUF model is loaded or using fallback."""
    orch = KingdomOrchestrator(models_dir=tmp_path)
    status = orch.get_model_status()
    
    assert "boss_qwen2.5" in status
    assert status["boss_qwen2.5"] is False  # Missing GGUF file in temp dir

def test_orchestrator_mock_gguf_boss_loaded(tmp_path):
    """Verify that when GGUF model file is present and llama_cpp loads, is_boss_loaded returns True."""
    gguf_file = tmp_path / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    gguf_file.write_bytes(b"dummy gguf bytes")

    mock_llama_mod = MagicMock()
    mock_llama_cls = MagicMock()
    mock_llama_mod.Llama = mock_llama_cls

    with patch.dict("sys.modules", {"llama_cpp": mock_llama_mod}):
        orch = KingdomOrchestrator(models_dir=tmp_path)
        assert orch.is_boss_loaded is True
        assert orch.get_model_status()["boss_qwen2.5"] is True
