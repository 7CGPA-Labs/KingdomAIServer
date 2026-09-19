"""
Kingdom AI Model Factory.
Provisions GGUF models, sidecar ministers, and SDXS-512 vision engine.
"""
from typing import Dict, Any, Optional
from pathlib import Path
from src.config import get_model_config
from src.core.hardware import HardwareManager

class ModelFactory:
    """Factory for loading Main Boss GGUF and Lean 3-Minister Council models."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_model_config()
        self.hardware = HardwareManager()
        self.models: Dict[str, Any] = {}

    def initialize_all((self) -> Dict[str, bool]:
        """Verify VRAM allocation and initialize model handles."""
        results = {}
        main_cfg = self.config.get("main_boss", {})
        self.hardware.verify_vram_budget(main_cfg.get("vram_budget_mb", 1100))
        self.hardware.register_allocation(main_cfg.get("vram_budget_mb", 1100))
        results["main_boss"] = True

        ministers = self.config.get("council_ministers", {})
        for name, spec in ministers.items():
            vram = spec.get("vram_budget_mb", 50)
            self.hardware.register_allocation(vram)
            results[name] = True

        return results
