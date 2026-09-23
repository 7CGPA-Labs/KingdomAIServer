"""
Unit tests for server entrypoint and Continue.dev config helper (V2 Engine).
"""
import pytest
from src.utils.continue_config import repair_continue_config
from src.utils.downloader import MODEL_RELEASES

def test_repair_continue_config(tmp_path, monkeypatch):
    """Test pure-Python Continue.dev configuration repair."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    res = repair_continue_config()
    assert res is True
    config_file = tmp_path / ".continue" / "config.json"
    assert config_file.exists()

def test_downloader_specs():
    """Test thin-client downloader specifications manifest for V2 GGUF & Lean Council models."""
    assert len(MODEL_RELEASES) == 3
    assert "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf" in MODEL_RELEASES
    assert "bge-small-en-v1.5-q4_k_m.gguf" in MODEL_RELEASES
