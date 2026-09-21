"""
GBNF Logit Sampling Grammars, Agent Personas & Turn Chaining for Main Boss V2.
Absorbs specialized reasoning tasks into Main Boss via agent role prompts and mathematical sampling constraints:
- Role A: Git Commit & Docstring Craftsman (Conventional Commits, JSDoc/Sphinx)
- Role B: Diff Search/Replace Realigner (CRLF/LF whitespace reconciliation)
- Role C: Security Escalation Auditor & GBNF Logit Sampling (JSON Schema logit mask)
- Role D: Mermaid.js & SVG Diagram Generator (Flowchart GBNF syntax constraint)
"""
import re
import json
from typing import Dict, Any, List, Optional
from src.prompts.templates import (
    GIT_CRAFTSMAN_ROLE_PROMPT,
    SECURITY_AUDITOR_ROLE_PROMPT,
    DIFF_REALIGNER_ROLE_PROMPT
)

# GBNF Grammars for C++ logit sampling
JSON_SECURITY_SCHEMA_GBNF = r"""
root ::= "{" ws "\"is_vulnerable\":" ws boolean "," ws "\"cwe_id\":" ws string_or_null "," ws "\"risk_score\":" ws number "," ws "\"mitigation\":" ws string "}"
boolean ::= "true" | "false"
string_or_null ::= "\"" [a-zA-Z0-9_\-\.\:\/ ]* "\"" | "null"
string ::= "\"" [a-zA-Z0-9_\-\.\:\/\, \t\n]* "\""
number ::= [0-9]+ "." [0-9]+ | [0-9]+
ws ::= [ \t\n]*
"""

MERMAID_DIAGRAM_GBNF = r"""
root ::= "flowchart " ("TD" | "LR") "\n" statement+
statement ::= [ \t]* [a-zA-Z0-9_]+ " --> " [a-zA-Z0-9_]+ "\n"
"""

CONVENTIONAL_COMMIT_REGEX = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-z0-9_-]+\))?: .+$"
)

class GitCommitCraftsman:
    """Role A: Conventional Commit & Docstring Generator."""

    @staticmethod
    def validate_commit_message(msg: str) -> bool:
        """Validate string matches Conventional Commits specification."""
        clean_msg = msg.strip().splitlines()[0] if msg else ""
        return bool(CONVENTIONAL_COMMIT_REGEX.match(clean_msg))

    @staticmethod
    def format_commit_prompt(git_diff: str) -> str:
        """Construct prompt for Conventional Commit generation with temperature=0.0."""
        return f"{GIT_CRAFTSMAN_ROLE_PROMPT}\n\nGit Diff:\n{git_diff}\n\nCommit Message:"

    @staticmethod
    def format_docstring_prompt(code: str, style: str = "jsdoc") -> str:
        """Construct prompt for JSDoc/Sphinx docstring generation."""
        return f"Generate a clean {style} docstring for the following code:\n\n{code}"


class DiffRealigner:
    """Role B: Diff Search/Replace Realigner (reconciles whitespace & CRLF/LF line endings)."""

    @staticmethod
    def reconcile_search_replace(file_content: str, search_block: str, replace_block: str) -> Dict[str, Any]:
        """
        Reconcile SEARCH/REPLACE blocks against target file contents regardless of CRLF/LF or minor whitespace differences.
        """
        # Normalize line endings to LF
        norm_file = file_content.replace("\r\n", "\n")
        norm_search = search_block.replace("\r\n", "\n").strip()
        norm_replace = replace_block.replace("\r\n", "\n").strip()

        if norm_search in norm_file:
            updated = norm_file.replace(norm_search, norm_replace, 1)
            # Restore original CRLF if target file had CRLF
            if "\r\n" in file_content:
                updated = updated.replace("\n", "\r\n")
            return {
                "success": True,
                "updated_content": updated,
                "search_lines": len(norm_search.splitlines()),
                "replace_lines": len(norm_replace.splitlines())
            }

        # Fuzzy line-by-line whitespace matching fallback
        file_lines = norm_file.splitlines()
        search_lines = norm_search.splitlines()

        if not search_lines:
            return {"success": False, "updated_content": file_content, "error": "Empty search block"}

        start_idx = -1
        for i in range(len(file_lines) - len(search_lines) + 1):
            match = True
            for j, s_line in enumerate(search_lines):
                if file_lines[i + j].strip() != s_line.strip():
                    match = False
                    break
            if match:
                start_idx = i
                break

        if start_idx != -1:
            end_idx = start_idx + len(search_lines)
            new_lines = file_lines[:start_idx] + norm_replace.splitlines() + file_lines[end_idx:]
            updated = "\n".join(new_lines)
            if "\r\n" in file_content:
                updated = updated.replace("\n", "\r\n")
            return {
                "success": True,
                "updated_content": updated,
                "search_lines": len(search_lines),
                "replace_lines": len(norm_replace.splitlines())
            }

        return {"success": False, "updated_content": file_content, "error": "Search block not found in file content"}


class SecurityAuditor:
    """Role C: Deep Security Escalation Auditor with GBNF logit sampling schema."""

    @staticmethod
    def get_gbnf_grammar() -> str:
        """Return GBNF logit sampling grammar string for llama.cpp."""
        return JSON_SECURITY_SCHEMA_GBNF

    @staticmethod
    def format_security_prompt(code_snippet: str) -> str:
        """Construct prompt for Security Auditor persona."""
        return f"{SECURITY_AUDITOR_ROLE_PROMPT}\n\nCode Snippet to Audit:\n{code_snippet}\n\nJSON Output:"

    @staticmethod
    def parse_and_validate_json_output(raw_output: str) -> Dict[str, Any]:
        """Validate LLM output strictly matches required JSON schema format."""
        try:
            # Extract JSON block
            match = re.search(r"\{.*\}", raw_output, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                if "is_vulnerable" in data and "risk_score" in data:
                    return {
                        "is_valid_schema": True,
                        "data": data
                    }
        except Exception:
            pass

        return {
            "is_valid_schema": False,
            "data": {"is_vulnerable": False, "cwe_id": None, "risk_score": 0.0, "mitigation": "Schema parse error"}
        }


class MermaidDiagramGenerator:
    """Role D: Mermaid.js & SVG Diagram Generator with GBNF flowchart syntax enforcement."""

    @staticmethod
    def get_gbnf_grammar() -> str:
        """Return GBNF logit sampling grammar string for Mermaid flowcharts."""
        return MERMAID_DIAGRAM_GBNF

    @staticmethod
    def validate_mermaid_syntax(code: str) -> bool:
        """Validate flowchart TD/LR syntax and node transition arrows."""
        clean_code = code.strip()
        lines = clean_code.splitlines()
        if not lines:
            return False
        
        has_flowchart_hdr = any(l.strip().startswith("flowchart ") or l.strip().startswith("graph ") for l in lines)
        has_transitions = any("-->" in l or "---" in l for l in lines)

        return has_flowchart_hdr and has_transitions

    @staticmethod
    def format_diagram_prompt(description: str) -> str:
        """Construct prompt for Mermaid diagram generation."""
        return f"Generate a valid Mermaid.js flowchart diagram for:\n{description}\n\nMermaid Code:\n```mermaid\n"


class AgentPersonaChain:
    """Manager for Main Boss agent personas and GBNF grammar constraints."""

    def __init__(self):
        self.git_craftsman = GitCommitCraftsman()
        self.diff_realigner = DiffRealigner()
        self.security_auditor = SecurityAuditor()
        self.diagram_generator = MermaidDiagramGenerator()

    def get_persona_spec(self, persona_name: str) -> Dict[str, Any]:
        """Get agent persona configuration, system prompt, and GBNF grammar."""
        name = persona_name.upper()

        if "GIT" in name or "COMMIT" in name:
            return {
                "persona": "ROLE_A_GIT_CRAFTSMAN",
                "system_prompt": GIT_CRAFTSMAN_ROLE_PROMPT,
                "temperature": 0.0,
                "gbnf_grammar": None
            }
        elif "DIFF" in name or "REALIGN" in name:
            return {
                "persona": "ROLE_B_DIFF_REALIGNER",
                "system_prompt": DIFF_REALIGNER_ROLE_PROMPT,
                "temperature": 0.0,
                "gbnf_grammar": None
            }
        elif "SECURITY" in name or "AUDIT" in name:
            return {
                "persona": "ROLE_C_SECURITY_AUDITOR",
                "system_prompt": SECURITY_AUDITOR_ROLE_PROMPT,
                "temperature": 0.1,
                "gbnf_grammar": JSON_SECURITY_SCHEMA_GBNF
            }
        elif "DIAGRAM" in name or "MERMAID" in name:
            return {
                "persona": "ROLE_D_DIAGRAM_GENERATOR",
                "system_prompt": "You are Diagram Generator. Generate valid Mermaid.js flowcharts.",
                "temperature": 0.2,
                "gbnf_grammar": MERMAID_DIAGRAM_GBNF
            }
        else:
            return {
                "persona": "MAIN_BOSS",
                "system_prompt": "You are Main Boss, lead autonomous AI developer engine.",
                "temperature": 0.7,
                "gbnf_grammar": None
            }
