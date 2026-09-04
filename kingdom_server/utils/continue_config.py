"""
Continue.dev VS Code Extension configuration utility.
Auto-configures ~/.continue/config.json to connect cleanly to Kingdom AI Server at http://127.0.0.1:58420.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger("kingdom.continue_config")

DEFAULT_KINGDOM_MODEL = {
    "title": "Kingdom AI Server (Qwen2.5-Coder)",
    "provider": "openai",
    "model": "qwen2.5-coder-1.5b",
    "apiBase": "http://127.0.0.1:58420/v1",
    "apiKey": "EMPTY"
}

DEFAULT_TAB_MODEL = {
    "title": "Kingdom Autocomplete (Granite 128M)",
    "provider": "openai",
    "model": "granite-code-128m",
    "apiBase": "http://127.0.0.1:58420/v1",
    "apiKey": "EMPTY"
}


def repair_continue_config() -> bool:
    """Repairs or creates ~/.continue/config.json with Kingdom AI Server endpoints."""
    continue_dir = Path.home() / ".continue"
    config_path = continue_dir / "config.json"

    continue_dir.mkdir(parents=True, exist_ok=True)

    config_data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception:
            config_data = {}

    if "models" not in config_data or not isinstance(config_data["models"], list):
        config_data["models"] = []

    # Ensure Kingdom AI model is present
    has_kingdom = any(m.get("apiBase") == "http://127.0.0.1:58420/v1" and m.get("model") == "qwen2.5-coder-1.5b" for m in config_data["models"])
    if not has_kingdom:
        config_data["models"].insert(0, DEFAULT_KINGDOM_MODEL)

    # Set tab autocomplete model
    config_data["tabAutocompleteModel"] = DEFAULT_TAB_MODEL

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    logger.info(f"Successfully auto-configured Continue.dev settings at {config_path}")
    return True
