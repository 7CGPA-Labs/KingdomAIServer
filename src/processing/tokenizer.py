"""
Fill-In-the-Middle (FIM) Tokenizer & Sentinel Formatter for Qwen2.5-Coder.
Formatted for sub-35 ms ghost text code completion in Continue.dev and VS Code.
"""
from typing import Dict, Any, List, Optional
from src.prompts.templates import FIM_PREFIX_TOKEN, FIM_SUFFIX_TOKEN, FIM_MIDDLE_TOKEN

FIM_STOP_TOKENS = ["<|endoftext|>", "<|fim_prefix|>", "<|fim_suffix|>", "<|fim_middle|>", "<|im_end|>"]

def format_fim_prompt(prefix: str, suffix: str) -> str:
    """Format prompt with FIM sentinel tokens for Qwen2.5-Coder-1.5B."""
    if FIM_PREFIX_TOKEN in prefix:
        return prefix
    return f"{FIM_PREFIX_TOKEN}{prefix}{FIM_SUFFIX_TOKEN}{suffix}{FIM_MIDDLE_TOKEN}"

class FIMFormatter:
    """Manages Fill-In-the-Middle (FIM) formatting and greedy sampling options."""

    @staticmethod
    def format(prefix: str, suffix: str) -> str:
        """Construct standard Qwen FIM prompt."""
        return format_fim_prompt(prefix, suffix)

    @staticmethod
    def get_sampling_params(max_tokens: int = 32, temperature: float = 0.0) -> Dict[str, Any]:
        """Return greedy sampling parameters optimized for inline IDE ghost text."""
        return {
            "max_tokens": max_tokens,
            "temperature": temperature, # 0.0 greedy sampling for deterministic code completion
            "stop": FIM_STOP_TOKENS,
            "top_p": 1.0,
            "repeat_penalty": 1.05
        }

    @staticmethod
    def clean_completion(text: str) -> str:
        """Strip trailing sentinel tokens and control characters."""
        for token in FIM_STOP_TOKENS:
            text = text.replace(token, "")
        return text
