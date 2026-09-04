"""
Unit tests for model file verifier and integrity checker.
"""
import pytest
from pathlib import Path
from kingdom_server.utils.verifier import ModelVerifier, MODEL_MANIFEST

def test_model_manifest_completeness():
    """Verify all 9 models are specified in MODEL_MANIFEST."""
    assert len(MODEL_MANIFEST) == 9
    assert "qwen2.5-coder-1.5b-onnx" in MODEL_MANIFEST
    assert "all-MiniLM-L6-v2.onnx" in MODEL_MANIFEST
    assert "bge-small-en-v1.5.onnx" in MODEL_MANIFEST
    assert "bge-reranker-base.onnx" in MODEL_MANIFEST
    assert "codeberta-base.onnx" in MODEL_MANIFEST
    assert "granite-code-128m.onnx" in MODEL_MANIFEST
    assert "nli-deberta-v3-small.onnx" in MODEL_MANIFEST
    assert "codebert-vulnerability.onnx" in MODEL_MANIFEST
    assert "MobileDiffusion-LCM.onnx" in MODEL_MANIFEST

def test_model_verifier_missing_files(tmp_path):
    """Test model verifier reports missing status when models dir is empty."""
    verifier = ModelVerifier(models_dir=tmp_path)
    summary = verifier.get_summary()
    assert summary["total"] == 9
    assert summary["valid"] == 0
    assert summary["missing"] == 9
    assert summary["all_healthy"] is False

def test_model_verifier_corrupt_file(tmp_path):
    """Test model verifier flags 0-byte corrupt files."""
    dummy_file = tmp_path / "all-MiniLM-L6-v2.onnx"
    dummy_file.write_bytes(b"") # Empty 0-byte file

    verifier = ModelVerifier(models_dir=tmp_path)
    spec = MODEL_MANIFEST["all-MiniLM-L6-v2.onnx"]
    res = verifier.verify_single_model("all-MiniLM-L6-v2.onnx", spec)
    
    assert res["status"] == "corrupt"
    assert "0 bytes" in res["message"]

def test_model_verifier_valid_file(tmp_path):
    """Test model verifier marks model files meeting size requirements as valid."""
    dummy_file = tmp_path / "all-MiniLM-L6-v2.onnx"
    dummy_file.write_bytes(b"dummy model binary data content")

    verifier = ModelVerifier(models_dir=tmp_path)
    spec = MODEL_MANIFEST["all-MiniLM-L6-v2.onnx"].copy()
    spec["approx_size_mb"] = 0.00001
    res = verifier.verify_single_model("all-MiniLM-L6-v2.onnx", spec)
    
    assert res["status"] == "valid"
    assert res["actual_mb"] >= 0
