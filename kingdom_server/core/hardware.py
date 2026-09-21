"""
Hardware acceleration fallback engine & VRAM memory safety manager for Kingdom AI Server V2.
"""
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path
import logging
from src.core.hardware import HardwareManager, STATIC_VRAM_CEILING_MB

logger = logging.getLogger("kingdom.hardware")

class ExecutionProviderHandler:
    def __init__(self, next_handler: Optional["ExecutionProviderHandler"] = None):
        self.next_handler = next_handler

    def handle(self, available_providers: List[str]) -> Tuple[str, str]:
        if self.next_handler:
            return self.next_handler.handle(available_providers)
        return ("CPUExecutionProvider", "CPU (AVX2 Fallback)")

class DirectMLHandler(ExecutionProviderHandler):
    def handle(self, available_providers: List[str]) -> Tuple[str, str]:
        if "DmlExecutionProvider" in available_providers or "DirectML" in available_providers:
            return ("DmlExecutionProvider", "DirectML GPU (DirectX 12)")
        return super().handle(available_providers)

class HardwareAccelerationEngine:
    """Master hardware acceleration & VRAM safety manager."""
    
    def __init__(self):
        self.hw_manager = HardwareManager()
        self.chain = DirectMLHandler()

    def get_available_providers(self) -> List[str]:
        diag = self.hw_manager.detect_environment()
        if diag["directml_supported"]:
            return ["DmlExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def resolve_onnx_provider(self) -> Tuple[str, str]:
        providers = self.get_available_providers()
        return self.chain.handle(providers)

    def resolve_genai_backend(self) -> str:
        diag = self.hw_manager.detect_environment()
        return f"llama.cpp GGUF ({diag['selected_provider']})"

    def get_shader_cache_dir(self) -> Path:
        from kingdom_server.utils import get_base_dir
        cache_dir = get_base_dir() / "shader_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def get_active_tiers(self) -> Dict[str, Any]:
        diag = self.hw_manager.detect_environment()
        return {
            "onnx_provider": "DirectML" if diag["directml_supported"] else "CPU",
            "ministers_tier": diag["selected_provider"],
            "boss_tier": f"llama.cpp GGUF ({diag['selected_provider']})",
            "vram_ceiling_mb": STATIC_VRAM_CEILING_MB,
            "shader_cache_path": str(self.get_shader_cache_dir())
        }
