"""
Unit tests for CLI commands including ask/prompt and model downloader.
"""
import pytest
from typer.testing import CliRunner
from kingdom_server.cli.commands import app
from kingdom_server.utils.downloader import MODEL_DOWNLOAD_URLS

runner = CliRunner()

def test_cli_ask_prompt():
    """Test kingdom ask 'prompt' command directly from CLI."""
    result = runner.invoke(app, ["ask", "Write a simple function to return hello world."])
    assert result.exit_code == 0
    assert "Kingdom AI Server Response" in result.output

def test_cli_download_urls_manifest():
    """Test downloader manifest has URLs for all 9 models."""
    assert len(MODEL_DOWNLOAD_URLS) == 9
    assert "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf" in MODEL_DOWNLOAD_URLS
    assert "all-MiniLM-L6-v2.onnx" in MODEL_DOWNLOAD_URLS
