"""
Unit tests for server entrypoint and Continue.dev config helper.
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
    """Test thin-client downloader specifications manifest for all 9 ONNX models."""
    assert len(MODEL_HF_SPECS) == 9
    assert "qwen2.5-coder-1.5b-onnx" in MODEL_HF_SPECS
    assert MODEL_HF_SPECS["qwen2.5-coder-1.5b-onnx"]["repo_id"] == "onnx-community/Qwen2.5-Coder-1.5B-Instruct-ONNX"
    assert "all-MiniLM-L6-v2.onnx" in MODEL_HF_SPECS
