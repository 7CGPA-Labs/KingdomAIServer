"""
Models Adapter for Kingdom AI Studio V3.
Maps local GGUF models and upgrade catalogs into Slint ModelCardItem representations.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import slint

from src.utils import get_models_dir
from src.utils.verifier import UPGRADE_MODELS, MODEL_MANIFEST

# Supported models catalog for Kingdom AI Studio V3
STUDIO_MODELS_CATALOG: Dict[str, Dict[str, Any]] = {
    "qwen2.5-coder-1.5b": {
        "id": "qwen2.5-coder-1.5b",
        "name": "Qwen 2.5 Coder 1.5B",
        "repo_id": "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
        "filename": "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        "approx_size_mb": 1100,
        "vram_required_mb": 1100,
        "description": "Default Main Boss engine. Fast and lightweight."
    },
    "qwen2.5-coder-3b": {
        "id": "qwen2.5-coder-3b",
        "name": "Qwen 2.5 Coder 3B",
        "repo_id": "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
        "filename": "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
        "approx_size_mb": 2020,
        "vram_required_mb": 2900,
        "description": "Balanced high-performance coding model (3B parameters)."
    },
    "qwen3-coder-1.7b": {
        "id": "qwen3-coder-1.7b",
        "name": "Qwen 3 Coder 1.7B",
        "repo_id": "Qwen/Qwen3-Coder-1.7B-Instruct-GGUF",
        "filename": "qwen3-coder-1.7b-instruct-q4_k_m.gguf",
        "approx_size_mb": 1250,
        "vram_required_mb": 1800,
        "description": "Next-gen ultra-fast agentic coding model (1.7B parameters)."
    },
    "qwen3-coder-4b": {
        "id": "qwen3-coder-4b",
        "name": "Qwen 3 Coder 4B",
        "repo_id": "Qwen/Qwen3-Coder-4B-Instruct-GGUF",
        "filename": "qwen3-coder-4b-instruct-q4_k_m.gguf",
        "approx_size_mb": 2800,
        "vram_required_mb": 4200,
        "description": "Advanced reasoning & repo-scale architect (4B parameters)."
    },
    "deepseek-coder-1.3b": {
        "id": "deepseek-coder-1.3b",
        "name": "DeepSeek Coder 1.3B",
        "repo_id": "deepseek-ai/deepseek-coder-1.3b",
        "filename": "deepseek-coder-1.3b-instruct-q4_k_m.gguf",
        "approx_size_mb": 950,
        "vram_required_mb": 1050,
        "description": "Ultra-lightweight multi-language code completion engine."
    }
}


def get_model_spec(model_id_or_name: str) -> Optional[Dict[str, Any]]:
    """Resolve a model specification by ID, filename, or alias."""
    query = model_id_or_name.lower().strip()
    for mid, spec in STUDIO_MODELS_CATALOG.items():
        if query in (mid, spec["name"].lower(), spec["filename"].lower()):
            return spec
    # Check UPGRADE_MODELS fallback
    for mid, spec in UPGRADE_MODELS.items():
        if query in (mid, spec.get("name", "").lower(), spec.get("filename", "").lower()):
            return {
                "id": mid,
                "name": spec.get("name", mid),
                "repo_id": spec.get("repo_id", ""),
                "filename": spec.get("filename", f"{mid}.gguf"),
                "approx_size_mb": spec.get("approx_size_mb", 1500),
                "vram_required_mb": spec.get("vram_required_mb", 2000),
                "description": spec.get("description", "")
            }
    return None


def get_model_filepath(model_id_or_name: str, models_dir: Optional[Path] = None) -> Optional[Path]:
    """Get the absolute path to a model file on disk."""
    spec = get_model_spec(model_id_or_name)
    if not spec:
        return None
    mdir = Path(models_dir or get_models_dir())
    return mdir / spec["filename"]


def build_slint_model_list(active_model_id_or_name: str, models_dir: Optional[Path] = None) -> slint.ListModel:
    """Build a slint.ListModel populated with ModelCardItem dictionaries."""
    mdir = Path(models_dir or get_models_dir())
    items = []

    active_query = active_model_id_or_name.lower().strip()

    for mid, spec in STUDIO_MODELS_CATALOG.items():
        file_path = mdir / spec["filename"]
        is_installed = False
        actual_disk_mb = 0.0

        if file_path.exists():
            size = file_path.stat().st_size
            # Require minimum size (at least 10 MB) to be considered installed
            if size >= 10 * 1024 * 1024:
                is_installed = True
                actual_disk_mb = round(size / (1024 * 1024), 1)

        is_active = (
            active_query == mid or
            active_query == spec["name"].lower() or
            active_query == spec["filename"].lower() or
            mid in active_query
        )

        item = {
            "id": spec["id"],
            "name": spec["name"],
            "repo_id": spec["repo_id"],
            "approx_size_mb": spec["approx_size_mb"],
            "vram_required_mb": spec["vram_required_mb"],
            "is_installed": is_installed,
            "is_active": is_active,
            "actual_disk_mb": actual_disk_mb,
        }
        items.append(item)

    return slint.ListModel(items)
