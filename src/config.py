"""
Kingdom AI Server V2 Configuration Loader Module.
Loads YAML configuration files from config/ with fallback defaults.
"""
import yaml
from pathlib import Path
from typing import Dict, Any

from src.utils import get_base_dir

_base = Path(__file__).parent.parent.resolve()

# Split paths to handle running inside a read-only ZipApp (.pyz)
if _base.is_file() and _base.suffix == '.pyz':
    # Inside ZipApp: _base = ...\bin\kingdom.pyz
    APP_ROOT = _base
else:
    # Running from raw source tree
    APP_ROOT = _base

CONFIG_DIR = APP_ROOT / "config"
DATA_DIR = get_base_dir() / "data"

def ensure_data_directories() -> None:
    """Create data subdirectories if missing."""
    (DATA_DIR / "cache").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "embeddings").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "vectordb").mkdir(parents=True, exist_ok=True)

def load_yaml_config(file_name: str) -> Dict[str, Any]:
    """Load a YAML file from the config directory."""
    if APP_ROOT.is_file() and APP_ROOT.suffix == '.pyz':
        import zipfile
        try:
            with zipfile.ZipFile(APP_ROOT, 'r') as z:
                with z.open(f"config/{file_name}") as f:
                    return yaml.safe_load(f) or {}
        except (KeyError, FileNotFoundError):
            return {}
        except Exception:
            return {}
    else:
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
            "hardware": {"execution_provider": "GPU", "strict_gpu": True, "n_gpu_layers": -1, "max_static_vram_mb": 1250},
            "main_boss": {"model_id": "qwen2.5-coder-1.5b-instruct", "vram_budget_mb": 1100, "strict_gpu": True, "n_gpu_layers": -1},
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
