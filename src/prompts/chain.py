"""
GBNF Logit Sampling Grammars & Agent Turn Chaining.
Mathematically forces deterministic JSON and structural syntax from Main Boss.
"""

JSON_SECURITY_SCHEMA_GBNF = r"""
root ::= "{" ws "\"is_vulnerable\":" ws boolean "," ws "\"cwe_id\":" ws string_or_null "," ws "\"risk_score\":" ws number "}"
boolean ::= "true" | "false"
string_or_null ::= "\"" [a-zA-Z0-9_-]* "\"" | "null"
number ::= [0-9]+ "." [0-9]+ | [0-9]+
ws ::= [ \t\n]*
"""

MERMAID_DIAGRAM_GBNF = r"""
root ::= "flowchart " ("TD" | "LR") "\n" statement+
statement ::= [ \t]* [a-zA-Z0-9_]+ " --> " [a-zA-Z0-9_]+ "\n"
"""
