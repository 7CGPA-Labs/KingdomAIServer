"""
GGUF Model Execution Orchestrator via llama.cpp.
Handles high-priority Fill-in-the-Middle (FIM) and streaming chat completions.
"""
from typing import Dict, Any, Generator, Optional
import os

class LlamaCppOrchestrator:
    """Orchestrates Main Boss GGUF LLM execution (Qwen2.5-Coder-1.5B)."""

    def __init__(self, model_path: Optional[str] = None, n_ctx: int = 4096, n_gpu_layers: int = -1):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.is_loaded = False
        self._llm = None

    def load_model(self) -> bool:
        """Load GGUF weights into llama.cpp with DirectML/CPU fallback."""
        try:
            import llama_cpp
            if self.model_path and os.path.exists(self.model_path):
                self._llm = llama_cpp.Llama(
                    model_path=self.model_path,
                    n_ctx=self.n_ctx,
                    n_gpu_layers=self.n_gpu_layers,
                    verbose=False
                )
                self.is_loaded = True
                return True
        except ImportError:
            pass
        return False

    def generate_completion(self, prompt: str, max_tokens: int = 256, stop: Optional[list] = None, temperature: float = 0.7) -> str:
        """Execute single-turn generation or FIM completion."""
        if self._llm:
            output = self._llm(
                prompt,
                max_tokens=max_tokens,
                stop=stop or [],
                temperature=temperature
            )
            return output["choices"][0]["text"]
        return "// GGUF model uninitialized - placeholder response"

    def stream_completion(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> Generator[str, None, None]:
        """Stream SSE completion deltas."""
        if self._llm:
            stream = self._llm(
                prompt,
                max_tokens=max_tokens,
                stream=True,
                temperature=temperature
            )
            for chunk in stream:
                yield chunk["choices"][0]["text"]
        else:
            yield "GGUF runtime uninitialized."
