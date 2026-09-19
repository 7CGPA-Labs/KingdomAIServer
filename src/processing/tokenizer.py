"""
Fill-In-the-Middle (FIM) Tokenizer & Sentinel Formatter for Qwen2.5-Coder.
"""
from src.prompts.templates import FIM_PREFIX_TOKEN, FIM_SUFFIX_TOKEN, FIM_MIDDLE_TOKEN

def format_fim_prompt(prefix: str, suffix: str) -> str:
    """Format prompt with FIM sentinel tokens for Qwen2.5-Coder-1.5B."""
    return f"{FIM_PREFIX_TOKEN}{prefix}{FIM_SUFFIX_TOKEN}{suffix}{FIM_MIDDLE_TOKEN}"
