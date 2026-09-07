"""
Hardware acceleration fallback engine implementing Chain of Responsibility pattern.
Cascading Resolution: [OpenVINOExecutionProvider / QNNExecutionProvider -> DmlExecutionProvider -> CPUExecutionProvider]
"""
from typing import List, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger("kingdom.hardware")

class ExecutionProviderHandler:
    def __init__(self, next_handler: Optional["ExecutionProviderHandler"] = None):
        self.next_handler = next_handler

    def handle(self, available_providers: List[str]) -> Tuple[str, str]:
        if self.next_handler:
            return self.next_handler.handle(available_providers)
        return ("CPUExecutionProvider", "CPU (AVX2 Fallback)")

class NPUHandler(ExecutionProviderHandler):
    def handle(self, available_providers: List[str]) -> Tuple[str, str]:
        for ep in ["OpenVINOExecutionProvider", "QNNExecutionProvider"]:
            if ep in available_providers:
                logger.debug(f"Selected NPU Execution Provider: {ep}")
                return (ep, "NPU Acceleration")
        return super().handle(available_providers)

class DirectMLHandler(ExecutionProviderHandler):
    def handle(self, available_providers: List[str]) -> Tuple[str, str]:
        if "DmlExecutionProvider" in available_providers:
            logger.debug("Selected DirectML Execution Provider (DirectX 12 GPU)")
            return ("DmlExecutionProvider", "DirectML GPU (DirectX 12)")
        return super().handle(available_providers)

class CPUHandler(ExecutionProviderHandler):
    def handle(self, available_providers: List[str]) -> Tuple[str, str]:
        if "CPUExecutionProvider" in available_providers:
            logger.debug("Selected CPU Execution Provider (AVX2)")
            return ("CPUExecutionProvider", "CPU (AVX2)")
        return super().handle(available_providers)

class HardwareAccelerationEngine:
    """Master hardware acceleration manager using Chain of Responsibility pattern."""
    
    def __init__(self):
        # Build the chain: NPU -> DirectML -> CPU
        self.chain = NPUHandler(DirectMLHandler(CPUHandler()))
        self._cached_onnx_provider: Optional[Tuple[str, str]] = None
        self._cached_genai_backend: Optional[str] = None

    def get_available_providers(self) -> List[str]:
        try:
            import onnxruntime as ort
            return ort.get_available_providers()
        except ImportError:
            return ["CPUExecutionProvider"]
        except Exception:
            return ["CPUExecutionProvider"]

    def resolve_onnx_provider(self) -> Tuple[str, str]:
        """Resolves the best ONNX execution provider according to 3-tier fallback."""
        if self._cached_onnx_provider is None:
            providers = self.get_available_providers()
            self._cached_onnx_provider = self.chain.handle(providers)
            logger.info(f"Hardware Acceleration Engine initialized: {self._cached_onnx_provider[1]}")
        return self._cached_onnx_provider

    def resolve_genai_backend(self) -> str:
        """Determines hardware backend for onnxruntime-genai-directml."""
        if self._cached_genai_backend is None:
            providers = self.get_available_providers()
            if "DmlExecutionProvider" in providers:
                self._cached_genai_backend = "ONNX Runtime GenAI DirectML (DirectX 12 GPU)"
            else:
                self._cached_genai_backend = "ONNX Runtime GenAI CPU (AVX2 Fallback)"
        return self._cached_genai_backend

    def get_shader_cache_dir(self) -> Path:
        from kingdom_server.utils import get_base_dir
        cache_dir = get_base_dir() / "shader_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def get_active_tiers(self) -> dict:
        onnx_provider, onnx_tier = self.resolve_onnx_provider()
        genai_tier = self.resolve_genai_backend()
        return {
            "onnx_provider": onnx_provider,
            "ministers_tier": onnx_tier,
            "boss_tier": genai_tier,
            "shader_cache_path": str(self.get_shader_cache_dir())
        }
