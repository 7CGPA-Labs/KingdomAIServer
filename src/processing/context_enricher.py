"""
Context Enricher for Kingdom AI Studio V3 & Server V2.
Unifies heuristic intent routing, persona guidelines, preprocessor security scanning,
and optional RAG repository retrieval into a cohesive orchestration layer.
"""
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from src.prompts.templates import HeuristicIntentRouter
from src.prompts.chain import AgentPersonaChain
from src.processing.preprocessor import Preprocessor

logger = logging.getLogger("kingdom.enricher")


class ContextEnricher:
    """Orchestrates multi-model persona selection, intent routing, and context enrichment."""

    def __init__(
        self,
        router: Optional[HeuristicIntentRouter] = None,
        persona_chain: Optional[AgentPersonaChain] = None,
        preprocessor: Optional[Preprocessor] = None,
        embedder: Optional[Any] = None,
        reranker: Optional[Any] = None,
        vector_store: Optional[Any] = None,
    ):
        self.router = router or HeuristicIntentRouter()
        self.persona_chain = persona_chain or AgentPersonaChain()
        self.preprocessor = preprocessor or Preprocessor()
        self.embedder = embedder
        self.reranker = reranker
        self.vector_store = vector_store

    def enrich_chat_context(
        self,
        msgs: List[Dict[str, str]],
        workspace_path: Optional[Path] = None
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any], float]:
        """Enrich chat messages with intent routing, persona instructions, RAG context, and security audits."""
        last_user_msg = ""
        for m in reversed(msgs):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break

        # 1. Intent routing
        route_info = self.router.route_intent(last_user_msg)
        target_agent = route_info.get("target_agent", "MAIN_BOSS")
        intent = route_info.get("intent", "GENERAL_CHAT")

        # 2. Persona spec
        persona_spec = self.persona_chain.get_persona_spec(target_agent)
        recommended_temp = persona_spec.get("temperature", 0.7)
        system_notes: List[str] = []

        if persona_spec.get("system_prompt"):
            system_notes.append(persona_spec["system_prompt"])

        # 3. Security vulnerability analysis injection
        clean_lower = last_user_msg.lower()
        if intent == "SECURITY_AUDIT" or "/security" in clean_lower or "audit security" in clean_lower:
            findings = self.preprocessor.scan_security_issues(last_user_msg)
            if findings:
                findings_summary = "\n".join([
                    f"- Line {f['line_number']}: {f['description']} (Severity: {f['severity']})"
                    for f in findings[:5]
                ])
                system_notes.append(f"Static Vulnerability Analysis Findings:\n{findings_summary}")

        # 4. RAG context enrichment (if workspace vector store is available)
        if (target_agent == "MINISTER_1_2_RAG" or "@workspace" in clean_lower) and self.embedder and self.vector_store:
            try:
                clean_query = last_user_msg.replace("@workspace", "").replace("/search", "").strip()
                if clean_query:
                    query_vec = self.embedder.embed_query(clean_query)
                    candidates = self.vector_store.search_similar(query_vec, top_k=5)
                    if candidates and self.reranker:
                        context_chunks = self.reranker.rerank(clean_query, candidates, top_k=3)
                        if context_chunks:
                            context_text = "\n".join(c.get("content", "") for c in context_chunks)
                            system_notes.append(f"Relevant workspace context from repository:\n{context_text}")
            except Exception as e:
                logger.debug("RAG context enrichment non-fatal notice: %s", e)

        # 5. Context trimming for oversized code inputs
        enriched_msgs: List[Dict[str, str]] = []
        for m in msgs:
            content = m.get("content", "")
            if len(content.splitlines()) > 150 and any(kw in content for kw in ("```", "def ", "class ", "function ")):
                content = self.preprocessor.trim_context(content, max_lines=120)
            enriched_msgs.append({"role": m.get("role", "user"), "content": content})

        # 6. Apply system instructions
        if system_notes:
            combined_sys = "\n\n".join(system_notes)
            if enriched_msgs and enriched_msgs[0].get("role") == "system":
                enriched_msgs[0]["content"] = combined_sys + "\n\n" + enriched_msgs[0]["content"]
            else:
                enriched_msgs.insert(0, {"role": "system", "content": combined_sys})

        return enriched_msgs, route_info, recommended_temp
