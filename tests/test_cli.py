"""
Unit tests for CLI commands including ask/prompt and huggingface_hub model auto-provisioning downloader.
"""
import pytest
from typer.testing import CliRunner
from kingdom_server.cli.commands import app
from kingdom_server.utils.downloader import MODEL_HF_SPECS

runner = CliRunner()

def test_cli_ask_prompt():
    """Test kingdom ask, plan, code, and sessions commands directly from CLI."""
    res_ask = runner.invoke(app, ["ask", "Write a simple function to return hello world.", "--no-auto-provision"])
    assert res_ask.exit_code == 0
    assert "Ask Agent Response" in res_ask.output

    res_plan = runner.invoke(app, ["plan", "Create a microservice architecture plan.", "--no-auto-provision"])
    assert res_plan.exit_code == 0
    assert "Plan Agent Response" in res_plan.output

    res_code = runner.invoke(app, ["code", "func main() {}", "--no-auto-provision"])
    assert res_code.exit_code == 0
    assert "Code Agent Response" in res_code.output

    res_sess = runner.invoke(app, ["sessions"])
    assert res_sess.exit_code == 0

def test_cli_download_hf_specs():
    """Test thin-client huggingface_hub downloader specs manifest for all 9 models."""
    assert len(MODEL_HF_SPECS) == 9
    assert "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf" in MODEL_HF_SPECS
    assert MODEL_HF_SPECS["qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"]["repo_id"] == "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"
    assert "all-MiniLM-L6-v2.onnx" in MODEL_HF_SPECS
    assert MODEL_HF_SPECS["all-MiniLM-L6-v2.onnx"]["repo_id"] == "Xenova/all-MiniLM-L6-v2"
