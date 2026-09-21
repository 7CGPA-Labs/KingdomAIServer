"""
Unit tests for server entrypoint and Continue.dev config helper (V2 Engine).
"""
import pytest
from kingdom_server.utils.continue_config import repair_continue_config
from kingdom_server.utils.downloader import MODEL_HF_SPECS

def test_repair_continue_config(tmp_path, monkeypatch):
    """Test pure-Python Continue.dev configuration repair."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    res = repair_continue_config()
    assert res is True
    config_file = tmp_path / ".continue" / "config.json"
    assert config_file.exists()

def test_downloader_hf_specs():
    """Test thin-client downloader specifications manifest for V2 GGUF & Lean Council models."""
    assert len(MODEL_HF_SPECS) == 4
    assert "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf" in MODEL_HF_SPECS
    assert MODEL_HF_SPECS["qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"]["repo_id"] == "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"
    assert "bge-small-en-v1.5-q4_k_m.gguf" in MODEL_HF_SPECS
