"""
FIM Token Templates, Main Boss System Prompts, Agent Persona Prompts, and Heuristic Intent Router.
Replaces Minister 1 fast-path intent classification with 0.01 ms prefix/rule-based matching.
"""
import re
import time
from typing import Dict, Any

FIM_PREFIX_TOKEN = "<|fim_prefix|>"
FIM_SUFFIX_TOKEN = "<|fim_suffix|>"
FIM_MIDDLE_TOKEN = "<|fim_middle|>"

MAIN_BOSS_SYSTEM_PROMPT = """You are Main Boss, the lead autonomous AI developer engine in Kingdom AI Server V2.
You have access to a Lean 2-Minister Council (Embedder, Re-Ranker) and zero-VRAM native utilities.
Your goal is to provide precise, high-performance code, refactoring, and architectural advice.
"""

GIT_CRAFTSMAN_ROLE_PROMPT = """You are Git Craftsman. Generate a concise Conventional Commit message based on the provided git diff.
Format strictly as `type(scope): description`.
"""

SECURITY_AUDITOR_ROLE_PROMPT = """You are Security Auditor. Scan the code snippet for security vulnerabilities (CWE, credential leaks, SQL injection, unsafe shell sinks).
Output strictly JSON matching the required GBNF schema.
"""

DIFF_REALIGNER_ROLE_PROMPT = """You are Diff Realigner. Reconcile SEARCH/REPLACE blocks against target file contents regardless of CRLF/LF whitespace differences.
Output the exact updated file content.
"""

class HeuristicIntentRouter:
    """Prefix and rule-based heuristic matcher for fast IDE request routing in 0.01 ms with 0 MB VRAM."""

    def route_intent(self, prompt: str, has_code_selection: bool = False, is_fim_request: bool = False) -> Dict[str, Any]:
        """Classify user intent in <0.05 ms using deterministic prefix and pattern rules."""
        start = time.perf_counter()
        p_lower = prompt.lower().strip()

        if is_fim_request or FIM_PREFIX_TOKEN in prompt:
            intent = "FIM_AUTOCOMPLETE"
            target_agent = "MAIN_BOSS_FIM"
        elif p_lower.startswith("@workspace") or p_lower.startswith("/search") or "find in repo" in p_lower:
            intent = "RAG_SEARCH"
            target_agent = "MINISTER_1_2_RAG"
        elif p_lower.startswith("/fix") or "fix bug" in p_lower or "traceback" in p_lower:
            intent = "BUG_FIX"
            target_agent = "MAIN_BOSS"
        elif p_lower.startswith("/explain") or "explain code" in p_lower or "what does this do" in p_lower:
            intent = "EXPLAIN"
            target_agent = "MAIN_BOSS"
        elif p_lower.startswith("/commit") or "git diff" in p_lower or "commit message" in p_lower:
            intent = "GIT_COMMIT"
            target_agent = "ROLE_A_GIT_CRAFTSMAN"
        elif p_lower.startswith("/security") or "audit security" in p_lower or "cwe" in p_lower:
            intent = "SECURITY_AUDIT"
            target_agent = "ROLE_C_SECURITY_AUDITOR"
        elif p_lower.startswith("/diagram") or "mermaid" in p_lower or "flowchart" in p_lower:
            intent = "DIAGRAM_GEN"
            target_agent = "ROLE_D_DIAGRAM_GENERATOR"
        elif has_code_selection:
            intent = "CODE_REFACTOR"
            target_agent = "MAIN_BOSS"
        else:
            intent = "GENERAL_CHAT"
            target_agent = "MAIN_BOSS"

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return {
            "intent": intent,
            "target_agent": target_agent,
            "route_time_ms": round(elapsed_ms, 5),
            "is_fast_path": True,
            "vram_mb": 0
        }
