"""
Kingdom AI Server V2 Configuration Loader Module.
Loads YAML configuration files from config/ with fallback defaults.
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

def ensure_data_directories() -> None:
    """Create data subdirectories if missing."""
    (DATA_DIR / "cache").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "embeddings").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "vectordb").mkdir(parents=True, exist_ok=True)

def load_yaml_config(file_name: str) -> Dict[str, Any]:
    """Load a YAML file from the config directory."""
    config_path = CONFIG_DIR / file_name
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def get_model_config() -> Dict[str, Any]:
    """Return model and hardware configuration dictionary."""
    config = load_yaml_config("model_config.yaml")
    if not config:
        # Fallback defaults if file missing
        return {
            "server": {"host": "127.0.0.1", "port": 58420},
            "hardware": {"execution_provider": "DirectML", "max_static_vram_mb": 1480},
            "main_boss": {"model_id": "qwen2.5-coder-1.5b-instruct", "vram_budget_mb": 1100},
            "council_ministers": {
                "minister_1_embedder": {"vram_budget_mb": 35, "embedding_dimension": 384},
                "minister_2_reranker": {"vram_budget_mb": 110},
                "minister_3_vision": {"vram_budget_mb": 230}
            }
        }
    return config

def get_logging_config() -> Dict[str, Any]:
    """Return logging configuration dictionary."""
    return load_yaml_config("logging_config.yaml")

# Ensure required directory structure exists on module import
ensure_data_directories()
