"""
Fill-In-the-Middle (FIM) Tokenizer & Sentinel Formatter for Qwen2.5-Coder.
Formatted for sub-35 ms ghost text code completion in Continue.dev and VS Code.
"""
from typing import Dict, Any, List, Optional
from src.prompts.templates import FIM_PREFIX_TOKEN, FIM_SUFFIX_TOKEN, FIM_MIDDLE_TOKEN

# Stop tokens to prevent run-on multiline code generation beyond current block
FIM_STOP_TOKENS = [
    "<|endoftext|>",
    "<|fim_prefix|>",
    "<|fim_suffix|>",
    "<|fim_middle|>",
    "<|im_end|>",
    "\n\n",  # Strict stop on double line break for clean 1-2 line ghost text
]

def format_fim_prompt(
    prefix: str,
    suffix: str = "",
    workspace_context: str = "",
    imports_header: str = ""
) -> str:
    """Format prompt with FIM sentinel tokens, AST imports, and workspace vector context."""
    if FIM_PREFIX_TOKEN in prefix:
        return prefix

    full_prefix = ""
    if workspace_context:
        full_prefix += f"/* Workspace Context:\n{workspace_context.strip()}\n*/\n"
    if imports_header:
        full_prefix += f"{imports_header.strip()}\n"
    full_prefix += prefix

    return f"{FIM_PREFIX_TOKEN}{full_prefix}{FIM_SUFFIX_TOKEN}{suffix}{FIM_MIDDLE_TOKEN}"

class FIMFormatter:
    """Manages Fill-In-the-Middle (FIM) formatting and greedy sampling options."""

    @staticmethod
    def format(
        prefix: str,
        suffix: str = "",
        workspace_context: str = "",
        imports_header: str = ""
    ) -> str:
        """Construct standard Qwen FIM prompt with injected AST context."""
        return format_fim_prompt(prefix, suffix, workspace_context, imports_header)

    @staticmethod
    def get_sampling_params(max_tokens: int = 24, temperature: float = 0.0) -> Dict[str, Any]:
        """Return greedy sampling parameters optimized for inline IDE ghost text (1-2 lines max)."""
        return {
            "max_tokens": min(max_tokens, 32),
            "temperature": 0.0,  # Pure greedy decoding for deterministic completions
            "stop": FIM_STOP_TOKENS,
            "top_p": 1.0,
            "repeat_penalty": 1.0
        }

    @staticmethod
    def clean_completion(completion: str, suffix: str = "") -> str:
        """Strip trailing sentinel tokens and avoid duplicate closing brackets."""
        for token in FIM_STOP_TOKENS:
            completion = completion.replace(token, "")

        # Deduplicate closing syntax brackets if already in the immediate suffix
        s_strip = suffix.lstrip()
        c_strip = completion.rstrip()
        if s_strip and c_strip:
            first_suffix_char = s_strip[0]
            if first_suffix_char in ")}]":
                if c_strip.endswith(first_suffix_char):
                    completion = c_strip[:-1]

        return completion
