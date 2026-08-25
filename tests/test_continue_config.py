"""
Unit tests for Continue.dev configuration validation.
"""
import json
import pytest

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
        ],
        "tabAutocompleteModel": {
            "title": "Kingdom Autocomplete (Granite 128M)",
            "provider": "openai",
            "model": "granite-code-128m",
            "apiBase": "http://127.0.0.1:58420/v1",
            "apiKey": "EMPTY"
        }
    }

    config_str = json.dumps(config_snippet)
    parsed = json.loads(config_str)

    assert "models" in parsed
    assert parsed["models"][0]["apiBase"] == "http://127.0.0.1:58420/v1"
    assert parsed["models"][0]["provider"] == "openai"
    assert parsed["tabAutocompleteModel"]["apiBase"] == "http://127.0.0.1:58420/v1"
