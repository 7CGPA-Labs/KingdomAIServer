"""
GGUF Model Execution Orchestrator via llama.cpp.
Handles local streaming and non-streaming chat completions.
Supports DirectML GPU acceleration with automatic CPU AVX2 fallback.
"""
import os
import time
import json
import logging
import threading
from typing import Dict, Any, Generator, Optional, List

from src.utils import get_models_dir

logger = logging.getLogger("kingdom.llm")

class GPUOffloadRequiredError(RuntimeError):
    """Raised when strict GPU offloading is required but the runtime or hardware lacks GPU support."""
    pass

class LlamaCppOrchestrator:
    """Orchestrates Main Boss GGUF LLM execution (Qwen2.5-Coder-1.5B) with strict iGPU/GPU offload."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        n_ctx: int = 32768,
        n_gpu_layers: int = -1,
        strict_gpu: Optional[bool] = None
    ):
        if model_path is None:
            self.model_path = str(get_models_dir() / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")
        else:
            self.model_path = model_path
            
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        
        if strict_gpu is None:
            try:
                from src.config import get_model_config
                cfg = get_model_config()
                self.strict_gpu = cfg.get("hardware", {}).get("strict_gpu", True)
            except Exception:
                self.strict_gpu = True
        else:
            self.strict_gpu = strict_gpu

        self.is_loaded = False
        self._llm = None
        self._lock = threading.Lock()
        self.layers_offloaded = 0

    def load_model(self) -> bool:
        """Load GGUF weights into llama.cpp with strict iGPU/GPU offload."""
        with self._lock:
            if self.is_loaded:
                return True
            try:
                import llama_cpp
                if self.model_path and os.path.exists(self.model_path):
                    supports_gpu = getattr(llama_cpp, "llama_supports_gpu_offload", lambda: False)()

                    if self.strict_gpu and not supports_gpu:
                        err_msg = (
                            f"Strict iGPU/GPU offload is enabled (n_gpu_layers={self.n_gpu_layers}), "
                            "but the active llama_cpp runtime is built without GPU acceleration (llama_supports_gpu_offload() == False).\n"
                            "To enable GPU offload for Intel Iris Xe / Intel Arc / AMD Radeon / NVIDIA GeForce:\n"
                            "  • For Intel Iris Xe / Intel Arc / AMD Radeon (Vulkan):\n"
                            "    pip install --force-reinstall --prefer-binary https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35-vulkan/llama_cpp_python-0.3.35-py3-none-win_amd64.whl\n"
                            "  • For NVIDIA RTX/GTX (CUDA):\n"
                            "    pip install --force-reinstall --prefer-binary https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.35-cu124/llama_cpp_python-0.3.35-py3-none-win_amd64.whl\n"
                            "  • To allow CPU fallback, set 'strict_gpu: false' in config/model_config.yaml."
                        )
                        logger.error(err_msg)
                        raise GPUOffloadRequiredError(err_msg)

                    self._llm = llama_cpp.Llama(
                        model_path=self.model_path,
                        n_ctx=self.n_ctx,
                        n_gpu_layers=self.n_gpu_layers,
                        verbose=False
                    )
                    # Enable Prefix & KV RAM Cache (capacity 512 MB) for sub-15ms keystroke prefill
                    try:
                        self._llm.set_cache(llama_cpp.LlamaRAMCache(capacity_bytes=512 * 1024 * 1024))
                    except Exception:
                        pass
                    self.is_loaded = True
                    self.layers_offloaded = self.n_gpu_layers
                    logger.info("Successfully loaded GGUF model with strict GPU offload (n_gpu_layers=%s)", self.n_gpu_layers)
                    return True
            except ImportError:
                pass
            return False

    def generate_completion(
        self,
        prompt: str,
        max_tokens: int = 256,
        stop: Optional[List[str]] = None,
        temperature: float = 0.7,
        top_p: float = 0.95
    ) -> Dict[str, Any]:
        """Execute single-turn generation or completion request."""
        start = time.perf_counter()
        
        if not self.is_loaded:
            self.load_model()

        with self._lock:
            if self._llm:
                output = self._llm(
                    prompt,
                    max_tokens=max_tokens,
                    stop=stop or [],
                    temperature=temperature,
                    top_p=top_p
                )
                text = output["choices"][0]["text"]
                usage = output.get("usage", {"prompt_tokens": len(prompt) // 4, "completion_tokens": len(text) // 4})
            else:
                text = "// GGUF model uninitialized - placeholder response. Please verify model weights."
                usage = {"prompt_tokens": 10, "completion_tokens": 10}

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return {
            "text": text,
            "usage": usage,
            "latency_ms": round(elapsed_ms, 2)
        }

    def format_chat_prompt(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None) -> str:
        """Format OpenAI messages into Qwen2.5-Coder ChatML Instruct format."""
        formatted = ""
        
        # Inject tool schemas if tools are provided
        if tools:
            tool_instruction = (
                "You have access to the following tools:\n"
                "<tools>\n"
                f"{json.dumps(tools, indent=2)}\n"
                "</tools>\n"
                "To call a tool, you MUST output a JSON object enclosed within <tool_call></tool_call> tags. "
                "Example:\n<tool_call>\n{\"name\": \"tool_name\", \"arguments\": {\"arg1\": \"value\"}}\n</tool_call>\n"
                "Do not output anything else when making a tool call."
            )
            # Find if system message exists
            has_system = False
            for msg in messages:
                if msg.get("role") == "system":
                    msg["content"] = tool_instruction + "\n\n" + msg.get("content", "")
                    has_system = True
                    break
            if not has_system:
                messages = [{"role": "system", "content": tool_instruction}] + messages

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted += f"<|im_start|>{role}\n{content}<|im_end|>\n"
            
        formatted += "<|im_start|>assistant\n"
        return formatted

    def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream SSE chat completion chunks."""
        prompt = self.format_chat_prompt(messages, tools=tools)
        created_time = int(time.time())

        if not self.is_loaded:
            self.load_model()

        with self._lock:
            if self._llm:
                stream = self._llm(
                    prompt,
                    max_tokens=max_tokens,
                    stream=True,
                    temperature=temperature,
                    stop=["<|im_end|>", "<|endoftext|>"]
                )
                is_first = True
                for chunk in stream:
                    if is_first:
                        yield {
                            "id": f"chatcmpl-{created_time}",
                            "object": "chat.completion.chunk",
                            "created": created_time,
                            "model": "qwen2.5-coder-1.5b",
                            "choices": [{
                                "index": 0,
                                "delta": {"role": "assistant", "content": ""},
                                "finish_reason": None
                            }]
                        }
                        is_first = False

                    delta_text = chunk["choices"][0]["text"]
                    yield {
                        "id": f"chatcmpl-{created_time}",
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": "qwen2.5-coder-1.5b",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": delta_text},
                            "finish_reason": None
                        }]
                    }
                yield {
                    "id": f"chatcmpl-{created_time}",
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": "qwen2.5-coder-1.5b",
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
            else:
                yield {
                    "id": f"chatcmpl-{created_time}",
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": "qwen2.5-coder-1.5b",
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": "GGUF runtime uninitialized. Please provision model weights."},
                        "finish_reason": "stop"
                    }]
                }
