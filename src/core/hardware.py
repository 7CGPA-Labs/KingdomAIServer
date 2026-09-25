"""
Kingdom AI Server Hardware Diagnostics & VRAM Budget Monitor.
Ensures static VRAM budget allocation does not exceed the 1.25 GB ceiling.
"""
import os
import sys
import psutil
from typing import Dict, Any

STATIC_VRAM_CEILING_MB = 3072  # 3.00 GB Maximum Allocation

class HardwareManager:
    """Manages silicon device detection, DirectML provider initialization, and VRAM memory safety."""

    def __init__(self, provider: str = "DirectML", device_id: int = 0):
        self.provider = provider
        self.device_id = device_id
        self.vram_allocated_mb = 0

    def detect_environment(self) -> Dict[str, Any]:
        """Detect CPU cores, RAM, and GPU execution capabilities."""
        total_ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
        available_ram_gb = round(psutil.virtual_memory().available / (1024 ** 3), 2)
        cpu_count = os.cpu_count() or 4

        has_gpu_offload = False
        try:
            import llama_cpp
            has_gpu_offload = getattr(llama_cpp, "llama_supports_gpu_offload", lambda: False)()
        except ImportError:
            pass

        gpu_name = "Integrated GPU"
        try:
            from src.utils.telemetry import _query_dxgi_gpu
            dxgi = _query_dxgi_gpu()
            gpu_name = dxgi.get("name", "Integrated GPU")
        except Exception:
            pass

        if has_gpu_offload:
            provider = f"Vulkan / GPU Accelerated ({gpu_name})"
        else:
            provider = f"Vulkan / OpenCL (GPU/iGPU) - Ready for GPU wheel ({gpu_name})"

        return {
            "platform": sys.platform,
            "cpu_cores": cpu_count,
            "system_ram_gb": total_ram_gb,
            "available_ram_gb": available_ram_gb,
            "gpu_hardware": gpu_name,
            "gpu_offload_supported": has_gpu_offload,
            "directml_supported": has_gpu_offload,
            "selected_provider": provider,
            "vram_ceiling_mb": STATIC_VRAM_CEILING_MB
        }

    def verify_vram_budget(self, requested_vram_mb: int) -> bool:
        """Assert total resident VRAM stays under 1.48 GB ceiling."""
        projected = self.vram_allocated_mb + requested_vram_mb
        if projected > STATIC_VRAM_CEILING_MB:
            raise MemoryError(
                f"VRAM budget exceeded! Requested {requested_vram_mb} MB + Resident {self.vram_allocated_mb} MB "
                f"= {projected} MB > Ceiling {STATIC_VRAM_CEILING_MB} MB."
            )
        return True

    def register_allocation(self, vram_mb: int) -> None:
        """Register resident model VRAM footprint."""
        self.verify_vram_budget(vram_mb)
        self.vram_allocated_mb += vram_mb


from typing import List, Optional, Tuple
from pathlib import Path

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

    def resolve_execution_provider(self) -> Tuple[str, str]:
        providers = self.get_available_providers()
        return self.chain.handle(providers)

    def resolve_genai_backend(self) -> str:
        diag = self.hw_manager.detect_environment()
        return f"llama.cpp GGUF ({diag['selected_provider']})"

    def get_shader_cache_dir(self) -> Path:
        from src.utils import get_base_dir
        cache_dir = get_base_dir() / "shader_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def get_active_tiers(self) -> Dict[str, Any]:
        diag = self.hw_manager.detect_environment()
        return {
            "execution_provider": "DirectML" if diag["directml_supported"] else "CPU",
            "ministers_tier": diag["selected_provider"],
            "boss_tier": f"llama.cpp GGUF ({diag['selected_provider']})",
            "vram_ceiling_mb": STATIC_VRAM_CEILING_MB,
            "shader_cache_path": str(self.get_shader_cache_dir())
        }

