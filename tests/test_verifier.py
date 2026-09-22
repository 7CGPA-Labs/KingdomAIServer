"""
Unit tests for model file verifier and integrity checker (V2 Engine).
"""
import pytest
from pathlib import Path
from src.utils.verifier import ModelVerifier, MODEL_MANIFEST

def test_model_manifest_completeness():
    """Verify all 4 V2 models (Main Boss GGUF + 3 Ministers) are specified in MODEL_MANIFEST."""
    assert len(MODEL_MANIFEST) == 4
    assert "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf" in MODEL_MANIFEST
    assert "bge-small-en-v1.5-q4_k_m.gguf" in MODEL_MANIFEST
    assert "bge-reranker-base-q4_k_m.gguf" in MODEL_MANIFEST
    assert "sdxs-512-0.9-1step-int8.gguf" in MODEL_MANIFEST

def test_model_verifier_missing_files(tmp_path):
    """Test model verifier reports missing status when models dir is empty."""
    verifier = ModelVerifier(models_dir=tmp_path)
    summary = verifier.get_summary()
    assert summary["total"] == 4
    assert summary["valid"] == 0
    assert summary["missing"] == 4
    assert summary["all_healthy"] is False

def test_model_verifier_corrupt_file(tmp_path):
    """Test model verifier flags 0-byte corrupt files."""
    dummy_file = tmp_path / "bge-small-en-v1.5-q4_k_m.gguf"
    dummy_file.write_bytes(b"") # Empty 0-byte file

    verifier = ModelVerifier(models_dir=tmp_path)
    spec = MODEL_MANIFEST["bge-small-en-v1.5-q4_k_m.gguf"]
    res = verifier.verify_single_model("bge-small-en-v1.5-q4_k_m.gguf", spec)
    
    assert res["status"] == "corrupt"
    assert "0 bytes" in res["message"]

def test_model_verifier_valid_file(tmp_path):
    """Test model verifier marks model files meeting size requirements as valid."""
    dummy_file = tmp_path / "bge-small-en-v1.5-q4_k_m.gguf"
    dummy_file.write_bytes(b"dummy model binary data content")

    verifier = ModelVerifier(models_dir=tmp_path)
    spec = MODEL_MANIFEST["bge-small-en-v1.5-q4_k_m.gguf"].copy()
    spec["approx_size_mb"] = 0.00001
    res = verifier.verify_single_model("bge-small-en-v1.5-q4_k_m.gguf", spec)
    
    assert res["status"] == "valid"
    assert res["actual_mb"] >= 0
