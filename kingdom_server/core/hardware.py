"""
Hardware acceleration fallback engine implementing Chain of Responsibility pattern.
Cascading Resolution: [OpenVINOExecutionProvider / QNNExecutionProvider -> DmlExecutionProvider -> CPUExecutionProvider]
"""
from typing import List, Optional, Tuple
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
                logger.info(f"Selected NPU Execution Provider: {ep}")
                return (ep, "NPU Acceleration")
        return super().handle(available_providers)

class DirectMLHandler(ExecutionProviderHandler):
    def handle(self, available_providers: List[str]) -> Tuple[str, str]:
        if "DmlExecutionProvider" in available_providers:
            logger.info("Selected DirectML Execution Provider (DirectX 12 GPU)")
            return ("DmlExecutionProvider", "DirectML GPU (DirectX 12)")
        return super().handle(available_providers)

class CPUHandler(ExecutionProviderHandler):
    def handle(self, available_providers: List[str]) -> Tuple[str, str]:
        if "CPUExecutionProvider" in available_providers:
            logger.info("Selected CPU Execution Provider (AVX2)")
            return ("CPUExecutionProvider", "CPU (AVX2)")
        return super().handle(available_providers)

class HardwareAccelerationEngine:
    """Master hardware acceleration manager using Chain of Responsibility pattern."""
    
    def __init__(self):
        # Build the chain: NPU -> DirectML -> CPU
        self.chain = NPUHandler(DirectMLHandler(CPUHandler()))

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
        providers = self.get_available_providers()
        return self.chain.handle(providers)

    def resolve_llama_backend(self) -> str:
        """Determines hardware backend for llama-cpp-python (DirectML/Vulkan/AVX2)."""
        providers = self.get_available_providers()
        if "DmlExecutionProvider" in providers:
            return "DirectML / Vulkan GPU"
        return "AVX2 CPU Fallback"

    def get_active_tiers(self) -> dict:
        onnx_provider, onnx_tier = self.resolve_onnx_provider()
        llama_tier = self.resolve_llama_backend()
        return {
            "onnx_provider": onnx_provider,
            "ministers_tier": onnx_tier,
            "boss_tier": llama_tier,
        }
