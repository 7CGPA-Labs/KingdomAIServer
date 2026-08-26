"""
Unit tests for CLI commands including ask/prompt and huggingface_hub model auto-provisioning downloader.
"""
import pytest
from typer.testing import CliRunner
from kingdom_server.cli.commands import app
from kingdom_server.utils.downloader import MODEL_HF_SPECS

runner = CliRunner()

def test_cli_ask_prompt():
    """Test kingdom ask 'prompt' command directly from CLI."""
    result = runner.invoke(app, ["ask", "Write a simple function to return hello world.", "--no-auto-provision"])
    assert result.exit_code == 0
    assert "Kingdom AI Server Response" in result.output

def test_cli_download_hf_specs():
    """Test thin-client huggingface_hub downloader specs manifest for all 9 models."""
    assert len(MODEL_HF_SPECS) == 9
    assert "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf" in MODEL_HF_SPECS
    assert MODEL_HF_SPECS["qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"]["repo_id"] == "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"
    assert "all-MiniLM-L6-v2.onnx" in MODEL_HF_SPECS
    assert MODEL_HF_SPECS["all-MiniLM-L6-v2.onnx"]["repo_id"] == "Xenova/all-MiniLM-L6-v2"
