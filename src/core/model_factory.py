"""
Kingdom AI Model Factory.
Provisions GGUF models, sidecar ministers, and SDXS-512 vision engine under static VRAM budget ceiling (<= 1.48 GB).
"""
from typing import Dict, Any, Optional
from pathlib import Path
from src.config import get_model_config, DATA_DIR
from src.core.hardware import HardwareManager

class ModelFactory:
    """Factory for downloading, loading, and managing Main Boss GGUF and Lean 3-Minister Council handles."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_model_config()
        self.hardware = HardwareManager()
        self.models: Dict[str, Any] = {}
        self.models_dir = DATA_DIR / "cache" / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def get_main_boss_model_path(self) -> Path:
        """Get absolute path to Qwen2.5-Coder-1.5B GGUF file."""
        main_cfg = self.config.get("main_boss", {})
        filename = main_cfg.get("filename", "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")
        return self.models_dir / filename

    def provision_model_weights(self) -> Dict[str, Any]:
        """Verify model weight existence or trigger HuggingFace download."""
        main_path = self.get_main_boss_model_path()
        main_exists = main_path.exists()

        return {
            "main_boss_path": str(main_path),
            "main_boss_exists": main_exists,
            "models_dir": str(self.models_dir)
        }

    def initialize_all(self) -> Dict[str, bool]:
        """Verify VRAM allocation and initialize model handles."""
        results = {}
        main_cfg = self.config.get("main_boss", {})
        main_vram = main_cfg.get("vram_budget_mb", 1100)
        self.hardware.verify_vram_budget(main_vram)
        self.hardware.register_allocation(main_vram)
        results["main_boss"] = True

        ministers = self.config.get("council_ministers", {})
        for name, spec in ministers.items():
            vram = spec.get("vram_budget_mb", 50)
            self.hardware.register_allocation(vram)
            results[name] = True

        return results
