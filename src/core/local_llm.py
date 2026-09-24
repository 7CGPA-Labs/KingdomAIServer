"""
GGUF Model Execution Orchestrator via llama.cpp.
Handles high-priority Fill-in-the-Middle (FIM) and streaming chat completions.
Supports DirectML GPU acceleration with automatic CPU AVX2 fallback.
"""
import os
import time
import threading
from typing import Dict, Any, Generator, Optional, List
from src.processing.tokenizer import FIMFormatter, format_fim_prompt

from src.utils import get_models_dir

class LlamaCppOrchestrator:
    """Orchestrates Main Boss GGUF LLM execution (Qwen2.5-Coder-1.5B)."""

    def __init__(self, model_path: Optional[str] = None, n_ctx: int = 8192, n_gpu_layers: int = -1):
        if model_path is None:
            self.model_path = str(get_models_dir() / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")
        else:
            self.model_path = model_path
            
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.is_loaded = False
        self._llm = None
        self._lock = threading.Lock()

    def load_model(self) -> bool:
        """Load GGUF weights into llama.cpp with DirectML/CPU fallback."""
        with self._lock:
            if self.is_loaded:
                return True
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

    def generate_fim_completion(self, prefix: str, suffix: str = "", max_tokens: int = 128) -> Dict[str, Any]:
        """Execute high-priority inline Fill-In-the-Middle (FIM) autocomplete (<35 ms target TTFT)."""
        prompt = format_fim_prompt(prefix, suffix)
        params = FIMFormatter.get_sampling_params(max_tokens=max_tokens, temperature=0.0)

        res = self.generate_completion(
            prompt,
            max_tokens=params["max_tokens"],
            stop=params["stop"],
            temperature=params["temperature"],
            top_p=params["top_p"]
        )

        cleaned_text = FIMFormatter.clean_completion(res["text"])
        res["text"] = cleaned_text
        res["is_fim"] = True
        return res

    def format_chat_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Format OpenAI messages into Qwen2.5-Coder ChatML Instruct format."""
        formatted = ""
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
        temperature: float = 0.7
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream SSE chat completion chunks."""
        prompt = self.format_chat_prompt(messages)
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
                    delta_text = chunk["choices"][0]["text"]
                    delta_payload = {"content": delta_text}
                    if is_first:
                        delta_payload["role"] = "assistant"
                        is_first = False
                        
                    yield {
                        "id": f"chatcmpl-{created_time}",
                        "object": "chat.completion.chunk",
                        "created": created_time,
                        "model": "qwen2.5-coder-1.5b",
                        "choices": [{
                            "index": 0,
                            "delta": delta_payload,
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
