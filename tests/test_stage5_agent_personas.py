"""
Unit Tests & GBNF Verification Suite for Stage 5: Main Boss Agent Personas & GBNF Grammars.
Verifies:
- Role A: Git Commit Craftsman Conventional Commits validation & formatting
- Role B: Diff Realigner search/replace reconciliation under CRLF/LF line-ending mismatches
- Role C: Security Escalation Auditor GBNF JSON schema sampling & validation
- Role D: Mermaid.js Diagram Generator GBNF syntax parsing
- AgentPersonaChain persona specification lookup
"""
from src.prompts.chain import (
    GitCommitCraftsman,
    DiffRealigner,
    SecurityAuditor,
    MermaidDiagramGenerator,
    AgentPersonaChain,
    JSON_SECURITY_SCHEMA_GBNF,
    MERMAID_DIAGRAM_GBNF
)

def test_git_commit_craftsman_validation():
    craftsman = GitCommitCraftsman()

    assert craftsman.validate_commit_message("feat(v2): implement Stage 5 agent personas") is True
    assert craftsman.validate_commit_message("fix: resolve null pointer exception in parser") is True
    assert craftsman.validate_commit_message("chore(deps): update requirements.txt") is True
    assert craftsman.validate_commit_message("docs: update README.md") is True

    # Rejects non-conventional commits
    assert craftsman.validate_commit_message("added a cool feature to server") is False
    assert craftsman.validate_commit_message("fixed bug in code") is False

def test_diff_realigner_crlf_lf_reconciliation():
    realigner = DiffRealigner()

    target_file = "def calculate():\r\n    a = 10\r\n    b = 20\r\n    return a + b\r\n"
    search_block = "def calculate():\n    a = 10\n    b = 20"
    replace_block = "def calculate():\n    a = 100\n    b = 200"

    res = realigner.reconcile_search_replace(target_file, search_block, replace_block)

    assert res["success"] is True
    assert "a = 100" in res["updated_content"]
    assert "b = 200" in res["updated_content"]

def test_security_auditor_gbnf_and_json_parsing():
    auditor = SecurityAuditor()

    grammar = auditor.get_gbnf_grammar()
    assert "root ::=" in grammar
    assert "is_vulnerable" in grammar
    assert "risk_score" in grammar

    raw_llm_json = '{"is_vulnerable": true, "cwe_id": "CWE-89", "risk_score": 8.5, "mitigation": "Use parameterized queries"}'
    parsed = auditor.parse_and_validate_json_output(raw_llm_json)

    assert parsed["is_valid_schema"] is True
    assert parsed["data"]["is_vulnerable"] is True
    assert parsed["data"]["risk_score"] == 8.5

def test_mermaid_diagram_generator():
    gen = MermaidDiagramGenerator()

    grammar = gen.get_gbnf_grammar()
    assert "flowchart" in grammar
    assert "-->" in grammar

    valid_mermaid = "flowchart TD\n    A[Client] --> B[FastAPI Gateway]\n    B --> C[Main Boss GGUF]\n"
    assert gen.validate_mermaid_syntax(valid_mermaid) is True

    invalid_mermaid = "This is not a diagram syntax."
    assert gen.validate_mermaid_syntax(invalid_mermaid) is False

def test_agent_persona_chain():
    chain = AgentPersonaChain()

    spec_git = chain.get_persona_spec("GIT_COMMIT")
    assert spec_git["persona"] == "ROLE_A_GIT_CRAFTSMAN"
    assert spec_git["temperature"] == 0.0

    spec_sec = chain.get_persona_spec("SECURITY_AUDIT")
    assert spec_sec["persona"] == "ROLE_C_SECURITY_AUDITOR"
    assert spec_sec["gbnf_grammar"] == JSON_SECURITY_SCHEMA_GBNF

    spec_diag = chain.get_persona_spec("MERMAID_DIAGRAM")
    assert spec_diag["persona"] == "ROLE_D_DIAGRAM_GENERATOR"
    assert spec_diag["gbnf_grammar"] == MERMAID_DIAGRAM_GBNF
