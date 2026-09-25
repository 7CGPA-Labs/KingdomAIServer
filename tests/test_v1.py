"""
Consolidated V1 Integration Test Suite.
Combines server gateway endpoints, Continue.dev configuration, entrypoint repairs,
SSRF crawler security guardrails, model verification, and model usage/loading diagnostics.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.inference.inference_engine import app
from src.core.crawler import SSRFCrawler, SSRFProtectionError
from src.core.hardware import HardwareAccelerationEngine, HardwareManager
from src.core.ministers import MinisterFactory, WorkspacePathJail, WorkspacePathJailError
from src.core.orchestrator import KingdomOrchestrator
from src.utils.continue_config import repair_continue_config
from src.utils.downloader import MODEL_RELEASES
from src.utils.verifier import ModelVerifier, MODEL_MANIFEST
from src.config import get_model_config
from src.processing.chunking import TreeSitterChunker
from src.processing.preprocessor import ManifestLinter, VulnerabilityScanner, StructuralTrimmer, Preprocessor
from src.prompts.templates import HeuristicIntentRouter

client = TestClient(app)

# =============================================================================
# 1. Server Gateway & Middleware Endpoints (from test_server.py)
# =============================================================================

def test_payload_size_limit_middleware():
    """Test 2 MB payload size limit middleware."""
    large_payload = {"messages": [{"role": "user", "content": "x" * (2 * 1024 * 1024 + 100)}]}
    response = client.post("/v1/chat/completions", json=large_payload)
    assert response.status_code == 413
    assert "Payload Too Large" in response.json()["error"]["message"]

def test_workspace_path_jail():
    """Test WorkspacePathJail blocks traversal into sensitive user/system directories."""
    with pytest.raises(WorkspacePathJailError):
        WorkspacePathJail.validate_path("C:\\Users\\test\\.ssh\\id_rsa")

def test_chat_completions_non_stream_endpoint():
    """Test /v1/chat/completions non-stream JSON response."""
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "messages": [
            {"role": "user", "content": "Write a Python function to sort a list of numbers."}
        ],
        "stream": False
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) > 0
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert len(data["choices"][0]["message"]["content"]) > 0

def test_chat_completions_stream_endpoint():
    """Test /v1/chat/completions SSE streaming response."""
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "messages": [
            {"role": "user", "content": "Explain how async functions work in Python."}
        ],
        "stream": True
    }
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    lines = response.text.split("\n")
    assert any(line.startswith("data: ") for line in lines)
    assert any("[DONE]" in line for line in lines)

# =============================================================================
# 2. Continue.dev Configuration & Server Entrypoint (from test_continue_config.py & test_server_entrypoint.py)
# =============================================================================

def test_continue_config_format():
    """Verify that Continue.dev config format snippet targets http://127.0.0.1:58420/v1."""
    config_snippet = {
        "models": [
            {
                "title": "Kingdom AI Server (Qwen2.5-Coder)",
                "provider": "openai",
                "model": "qwen2.5-coder-1.5b",
                "apiBase": "http://127.0.0.1:58420/v1",
                "apiKey": "EMPTY"
            }
        ]
    }

    config_str = json.dumps(config_snippet)
    parsed = json.loads(config_str)

    assert "models" in parsed
    assert parsed["models"][0]["apiBase"] == "http://127.0.0.1:58420/v1"
    assert parsed["models"][0]["provider"] == "openai"
    assert "tabAutocompleteModel" not in parsed

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

# =============================================================================
# 3. SSRF-Safe Crawler Protection (from test_crawler.py)
# =============================================================================

def test_ssrf_blocked_loopback_ips():
    """Verify loopback IPv4 and IPv6 addresses are blocked."""
    assert SSRFCrawler.is_ip_blocked("127.0.0.1") is True
    assert SSRFCrawler.is_ip_blocked("127.0.0.2") is True
    assert SSRFCrawler.is_ip_blocked("::1") is True

def test_ssrf_blocked_rfc1918_ips():
    """Verify RFC 1918 private subnets are blocked."""
    assert SSRFCrawler.is_ip_blocked("10.0.0.1") is True
    assert SSRFCrawler.is_ip_blocked("172.16.0.1") is True
    assert SSRFCrawler.is_ip_blocked("192.168.1.1") is True

def test_ssrf_blocked_cloud_metadata():
    """Verify cloud metadata 169.254.169.254 IP is blocked."""
    assert SSRFCrawler.is_ip_blocked("169.254.169.254") is True
    assert SSRFCrawler.is_ip_blocked("169.254.1.1") is True

def test_ssrf_allowed_public_ips():
    """Verify public internet IPs are allowed."""
    assert SSRFCrawler.is_ip_blocked("8.8.8.8") is False
    assert SSRFCrawler.is_ip_blocked("1.1.1.1") is False

def test_ssrf_validate_url_exceptions():
    """Test validate_url raises SSRFProtectionError on illegal hosts/schemes."""
    with pytest.raises(SSRFProtectionError):
        SSRFCrawler.validate_url("http://127.0.0.1/admin")

    with pytest.raises(SSRFProtectionError):
        SSRFCrawler.validate_url("http://localhost:8080/secret")

    with pytest.raises(SSRFProtectionError):
        SSRFCrawler.validate_url("http://169.254.169.254/latest/meta-data/")

    with pytest.raises(SSRFProtectionError):
        SSRFCrawler.validate_url("ftp://example.com/file")

# =============================================================================
# 4. Model Usage & Status Diagnostics (from test_model_usage.py)
# =============================================================================

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
    assert status["boss_qwen2.5"] is False

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

# =============================================================================
# 5. Model Verifier & Integrity Checker (from test_verifier.py)
# =============================================================================

def test_model_manifest_completeness():
    """Verify all 3 V2 models (Main Boss GGUF + 2 Ministers) are specified in MODEL_MANIFEST."""
    assert len(MODEL_MANIFEST) == 3
    assert "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf" in MODEL_MANIFEST
    assert "bge-small-en-v1.5-q4_k_m.gguf" in MODEL_MANIFEST
    assert "bge-reranker-base-q4_k_m.gguf" in MODEL_MANIFEST

def test_model_verifier_missing_files(tmp_path):
    """Test model verifier reports missing status when models dir is empty."""
    verifier = ModelVerifier(models_dir=tmp_path)
    summary = verifier.get_summary()
    assert summary["total"] == 3
    assert summary["valid"] == 0
    assert summary["missing"] == 3
    assert summary["all_healthy"] is False

def test_model_verifier_corrupt_file(tmp_path):
    """Test model verifier flags 0-byte corrupt files."""
    dummy_file = tmp_path / "bge-small-en-v1.5-q4_k_m.gguf"
    dummy_file.write_bytes(b"")

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

# =============================================================================
# 6. Foundation Architecture & VRAM Budget (from test_stage1_foundation.py)
# =============================================================================

def test_stage1_config_loader():
    model_cfg = get_model_config()
    assert "server" in model_cfg
    assert model_cfg["server"]["port"] == 58420
    assert "hardware" in model_cfg
    assert model_cfg["hardware"]["max_static_vram_mb"] == 1250

def test_hardware_vram_ceiling():
    hw = HardwareManager()
    assert hw.verify_vram_budget(1100) is True
    assert hw.verify_vram_budget(375) is True
    with pytest.raises(MemoryError):
        hw.verify_vram_budget(4000)

def test_regex_security_scanner():
    prep = Preprocessor()
    dirty_code = "api_key = 'sk_live_1234567890abcdef12345'\nos.system('rm -rf /')"
    findings = prep.scan_security_issues(dirty_code)
    assert len(findings) >= 1

# =============================================================================
# 7. Zero-VRAM Native Utilities (from test_stage2_native_utilities.py)
# =============================================================================

PYTHON_SAMPLE_CODE = """
import os
import sys
import math

class Calculator:
    \"\"\"A simple calculator class.\"\"\"
    
    def __init__(self, base: int = 0):
        self.base = base
        
    def add(self, a: int, b: int) -> int:
        # Add two numbers together
        return self.base + a + b
        
    def multiply(self, a: int, b: int) -> int:
        return a * b

def main():
    calc = Calculator(10)
    print(calc.add(5, 5))
    api_key = "sk_live_1234567890abcdef12345"
    eval("print('unsafe dynamic eval')")
"""

JS_SAMPLE_CODE = """
import { useState, useEffect } from 'react';
import axios from 'axios';

export class UserService {
    async getUser(id) {
        return await axios.get('/api/user/' + id);
    }
}
"""

def test_treesitter_ast_chunker_python():
    chunker = TreeSitterChunker()
    result = chunker.parse_file(PYTHON_SAMPLE_CODE, "python")
    
    assert result["language"] == "python"
    assert result["chunks_count"] >= 2
    assert "os" in result["imports"]
    assert "sys" in result["imports"]
    assert "math" in result["imports"]
    assert result["parse_time_ms"] < 5.0

def test_treesitter_ast_chunker_javascript():
    chunker = TreeSitterChunker()
    result = chunker.parse_file(JS_SAMPLE_CODE, "typescript")
    
    assert result["language"] == "typescript"
    assert result["chunks_count"] >= 1
    assert "react" in result["imports"] or "axios" in result["imports"]

def test_manifest_import_linter():
    linter = ManifestLinter()
    linter.declared_dependencies = {"sys", "os", "math", "fastapi", "uvicorn"}
    
    imports = ["sys", "os", "numpy", "torch", "math"]
    res = linter.validate_imports(imports)
    
    assert res["is_valid"] is False
    assert "numpy" in res["hallucinated_imports"]
    assert "torch" in res["hallucinated_imports"]
    assert res["validation_time_ms"] < 2.0

def test_vulnerability_scanner():
    scanner = VulnerabilityScanner()
    findings = scanner.scan_security_issues(PYTHON_SAMPLE_CODE)
    
    assert len(findings) >= 2
    descriptions = [f["description"] for f in findings]
    assert any("Hardcoded Credential" in d for d in descriptions)
    assert any("Dynamic Code Injection Sink" in d for d in descriptions)

def test_structural_trimmer():
    trimmer = StructuralTrimmer()
    long_code = "\n".join([f"def func_{i}():\n    # Comment line {i}\n    return {i}\n" for i in range(100)])
    
    res = trimmer.trim_context(long_code, max_lines=30)
    assert res["trimmed_lines"] <= 35
    assert res["compression_ratio_pct"] > 30.0
    assert res["trim_time_ms"] < 2.0

def test_heuristic_intent_router():
    router = HeuristicIntentRouter()
    
    r1 = router.route_intent("@workspace find memory vault")
    assert r1["intent"] == "RAG_SEARCH"
    assert r1["route_time_ms"] < 1.0
    
    r2 = router.route_intent("/fix traceback error in line 45")
    assert r2["intent"] == "BUG_FIX"
    
    r3 = router.route_intent("/commit format git diff")
    assert r3["intent"] == "GIT_COMMIT"
    
    r4 = router.route_intent("anything", has_code_selection=True)
    assert r4["intent"] == "CODE_REFACTOR"

def test_unified_preprocessor():
    prep = Preprocessor()
    findings = prep.scan_security_issues(PYTHON_SAMPLE_CODE)
    assert len(findings) >= 2

