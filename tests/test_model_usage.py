"""
Test suite to explicitly verify V2 GGUF & Lean Council model loading and status tracking.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.hardware import HardwareAccelerationEngine
from src.core.ministers import MinisterFactory, BaseMinister
from src.core.orchestrator import KingdomOrchestrator
from src.core.local_llm import LlamaCppOrchestrator

def test_ministers_model_loaded_property(tmp_path):
    """Verify is_model_loaded reports False when model files are missing and True when loaded."""
    hw_engine = HardwareAccelerationEngine()
    factory = MinisterFactory(hw_engine, models_dir=tmp_path)
    ministers = factory.create_all_ministers()

    for key, minister in ministers.items():
        assert minister.is_model_loaded is False, f"{minister.name} should report is_model_loaded=False when file missing"

def test_ministers_mock_model_session(tmp_path):
    """Verify that when GGUF model session is active, is_model_loaded reports True."""
    hw_engine = HardwareAccelerationEngine()
    
    dummy_model_file = tmp_path / "bge-small-en-v1.5-q4_k_m.gguf"
    dummy_model_file.write_bytes(b"dummy gguf bytes")

    mock_llama = MagicMock()
    with patch.dict("sys.modules", {"llama_cpp": mock_llama}):
        minister1 = MinisterFactory(hw_engine, models_dir=tmp_path).create_all_ministers()["minister_1"]
        minister1._load_session()
        assert minister1.is_model_loaded is True
        assert minister1.session == "active"

def test_orchestrator_boss_model_usage(tmp_path):
    """Verify orchestrator tracks whether Main Boss GGUF model is loaded or using fallback."""
    orch = KingdomOrchestrator(models_dir=tmp_path)
    status = orch.get_model_status()
    
    assert "boss_qwen2.5" in status
    assert status["boss_qwen2.5"] is False  # Missing GGUF file in temp path

def test_orchestrator_mock_gguf_boss_loaded(tmp_path):
    """Verify that when GGUF model file is present and llama_cpp loads, is_boss_loaded returns True."""
    gguf_file = tmp_path / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    gguf_file.write_bytes(b"dummy gguf bytes")

    mock_llama_mod = MagicMock()
    mock_llama_cls = MagicMock()
    mock_instance = MagicMock()
    mock_llama_cls.return_value = mock_instance
    mock_llama_mod.Llama = mock_llama_cls

    with patch.dict("sys.modules", {"llama_cpp": mock_llama_mod}):
        orch = KingdomOrchestrator(models_dir=tmp_path)
        orch._init_boss_llm()
        assert orch.is_boss_loaded is True
        assert orch.get_model_status()["boss_qwen2.5"] is True
