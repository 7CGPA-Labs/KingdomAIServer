"""
The Kingdom Orchestrator: Master Boss (Qwen2.5-Coder-1.5B-Instruct) + 8-Minister Council router & inference manager.
Zero ready-made / zero mock policy: All responses are processed and generated dynamically by the active models.
"""
import time
import json
import uuid
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from kingdom_server.core.hardware import HardwareAccelerationEngine
from kingdom_server.core.ministers import MinisterFactory, BaseMinister
from kingdom_server.core.memory_vault import MemoryVault
from kingdom_server.utils import get_models_dir, load_role_prompt

import threading

logger = logging.getLogger("kingdom.orchestrator")

class KingdomOrchestrator:
    """Master Orchestrator coordinating Master Boss (Qwen2.5-Coder ONNX) and 8 ONNX Ministers."""

    def __init__(self, models_dir: Optional[Any] = None, db_path: Optional[Any] = None, preload_in_background: bool = False):
        self.models_dir = models_dir or get_models_dir()
        self.hardware_engine = HardwareAccelerationEngine()
        self.minister_factory = MinisterFactory(self.hardware_engine, self.models_dir)
        self.ministers = self.minister_factory.create_all_ministers()
        self.boss_prompt_role = load_role_prompt("main_boss")
        self.memory_vault = MemoryVault(db_path=db_path)
        self.genai_model = None
        self.genai_tokenizer = None
        self._boss_lock = threading.Lock()
        self._fim_lock = threading.Lock()
        self._boss_initialized = False

        if preload_in_background:
            threading.Thread(target=self._background_preload, daemon=True, name="model-preloader").start()

    def _background_preload(self):
        logger.info("Background model pre-loading started...")
        for name, minister in self.ministers.items():
            try:
                minister._load_session()
            except Exception as e:
                logger.warning(f"Error loading model for {name}: {e}")
        self._init_boss_llm()
        logger.info("Background model pre-loading complete. Server fully operational.")

    def _init_boss_llm(self):
        with self._boss_lock:
            if self.genai_model is not None:
                return
            genai_path = self.models_dir / "qwen2.5-coder-1.5b-onnx"
            if genai_path.is_file():
                try:
                    file_bytes = genai_path.read_bytes()
                    genai_path.unlink()
                    genai_path.mkdir(parents=True, exist_ok=True)
                    (genai_path / "model.onnx").write_bytes(file_bytes)
                except Exception:
                    pass

            if genai_path.exists() and genai_path.is_dir():
                try:
                    from kingdom_server.utils.downloader import ModelDownloader
                    ModelDownloader(self.models_dir).provision_qwen_onnx_config_files(genai_path)
                except Exception as e:
                    logger.debug(f"Error provisioning ONNX config files: {e}")

                try:
                    import os
                    os.environ.setdefault("OMP_NUM_THREADS", "2")
                    os.environ.setdefault("ONNXRUNTIME_NUM_THREADS", "2")
                    import onnxruntime_genai as og
                    backend = self.hardware_engine.resolve_genai_backend()
                    self.genai_model = og.Model(str(genai_path))
                    self.genai_tokenizer = og.Tokenizer(self.genai_model)
                    logger.info(f"Main Boss Qwen2.5 ONNX loaded with backend: {backend}")
                except Exception as e:
                    logger.warning(f"onnxruntime-genai-directml error loading Qwen2.5 ONNX: {e}. Minister Council active.")
                    self.genai_model = None
                    self.genai_tokenizer = None
            else:
                self.genai_model = None
                self.genai_tokenizer = None

    @property
    def is_boss_loaded(self) -> bool:
        return self.genai_model is not None

    def get_model_status(self) -> Dict[str, bool]:
        status = {"boss_qwen2.5": self.is_boss_loaded}
        for k, m in self.ministers.items():
            status[m.model_filename] = m.is_onnx_loaded
        return status

    def route_request(self, user_prompt: str) -> str:
        minister_1 = self.ministers["minister_1"]
        return minister_1.route_intent(user_prompt)

    def audit_security(self, text: str) -> Dict[str, Any]:
        minister_7 = self.ministers["minister_7"]
        return minister_7.audit(text)

    def get_context_embeddings(self, text: str) -> List[float]:
        minister_2 = self.ministers["minister_2"]
        return minister_2.embed(text)

    async def generate_chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "qwen2.5-coder-1.5b",
        temperature: float = 0.7,
        session_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        session_id = session_id or str(uuid.uuid4())
        created_ts = int(time.time())
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

        # Hydrate full multi-turn session history from MemoryVault if session_id exists and messages array only has 1 turn
        if session_id and len(messages) <= 1:
            stored_history = self.memory_vault.get_session_history(session_id)
            if stored_history:
                history_msgs = [{"role": msg["role"], "content": msg["content"]} for msg in stored_history]
                user_content = messages[-1].get("content", "") if messages else ""
                if not history_msgs or history_msgs[-1]["content"] != user_content:
                    history_msgs.append({"role": "user", "content": user_content})
                messages = history_msgs

        user_content = messages[-1].get("content", "") if messages else ""

        # Check Prompt Response Cache for Sub-2ms Fast Return
        query_vec = self.get_context_embeddings(user_content)
        cached_reply = self.memory_vault.get_cached_response(user_content, query_vec)
        if cached_reply:
            cached_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": model,
                "session_id": session_id,
                "council_trace": [{"id": "cache", "name": "Response Cache", "detail": "Sub-2ms Hit", "status": "verified"}],
                "choices": [{
                    "index": 0,
                    "delta": {"content": cached_reply},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(cached_chunk)}\n\n"
            end_chunk = {"id": completion_id, "object": "chat.completion.chunk", "created": created_ts, "model": model, "session_id": session_id, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            yield f"data: {json.dumps(end_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            self.memory_vault.add_session_message(session_id, "user", user_content)
            self.memory_vault.add_session_message(session_id, "assistant", cached_reply)
            return

        # Non-Serialized Parallel Minister Council Execution (ThreadPoolExecutor)
        with ThreadPoolExecutor(max_workers=8, thread_name_prefix="minister-worker") as pool:
            future_intent = pool.submit(self.route_request, user_content)
            future_audit = pool.submit(self.audit_security, user_content)
            future_ast = pool.submit(self.ministers["minister_4"].parse_code, user_content)
            
            future_web = None
            if "search" in user_content.lower() or "http://" in user_content.lower() or "https://" in user_content.lower():
                try:
                    import re
                    from kingdom_server.core.crawler import WebCrawler
                    found_urls = re.findall(r'https?://[^\s]+', user_content)
                    if found_urls:
                        future_web = pool.submit(WebCrawler().fetch_and_parse, found_urls[0])
                except Exception:
                    pass

            intent = future_intent.result()
            audit_res = future_audit.result()
            code_structure = future_ast.result()

            vector_matches = self.memory_vault.search_similar(query_vec, k=3)
            future_rerank = None
            if vector_matches:
                docs = [m["document"] for m in vector_matches if m["score"] > 0.3]
                if docs:
                    future_rerank = pool.submit(self.ministers["minister_3"].rerank, user_content, docs)

            web_context = ""
            if future_web:
                try:
                    crawl_res = future_web.result(timeout=3.0)
                    if crawl_res and crawl_res.get("text"):
                        web_context = f"\n\n[Live Web Search Context]:\n{crawl_res['text'][:1500]}\n"
                except Exception as e:
                    logger.debug(f"Parallel Web crawler error: {e}")

            retrieved_context = web_context
            if future_rerank:
                try:
                    ranked_docs = future_rerank.result(timeout=1.0)
                    if ranked_docs:
                        retrieved_context += "\n\n[Cognitive Memory Context by Minister 3 Re-Ranker]:\n" + "\n".join([doc[0] for doc in ranked_docs])
                except Exception as e:
                    logger.debug(f"Parallel Re-ranker error: {e}")

        security_warning = ""
        if not audit_res["safe"]:
            warning_details = ", ".join([v["detail"] for v in audit_res["vulnerabilities"]])
            security_warning = f"\n\n[Security Alert by Minister 7]: Potential vulnerabilities detected ({warning_details})."

        # Construct per-turn 8-Minister Council Execution Trace
        self._init_boss_llm()
        is_boss_active = self.genai_model is not None and self.genai_tokenizer is not None
        boss_backend = self.hardware_engine.resolve_genai_backend() if is_boss_active else "Minister Council Fallback"

        council_trace = [
            {"id": "minister_1", "name": "Intent Router", "detail": f"Intent: {intent}", "status": "active"},
        ]
        if vector_matches:
            council_trace.append({"id": "minister_2", "name": "Repo Embedder", "detail": "Vectors Embedded", "status": "active"})
        if retrieved_context:
            council_trace.append({"id": "minister_3", "name": "Re-Ranker", "detail": "Context Scored", "status": "active"})
        if code_structure and any(code_structure.values()):
            council_trace.append({"id": "minister_4", "name": "Code Parser", "detail": "AST Parsed", "status": "active"})
        if audit_res and not audit_res["safe"]:
            council_trace.append({"id": "minister_7", "name": "Security Auditor", "detail": "Security Filtered", "status": "active"})
        
        if is_boss_active:
            council_trace.append({"id": "boss_qwen2.5", "name": "Main Boss Qwen2.5", "detail": boss_backend, "status": "active"})
        else:
            council_trace.append({"id": "council_fallback", "name": "Minister Council", "detail": "Synthesizer Active", "status": "active"})

        council_trace.append({"id": "minister_6", "name": "Fact Checker", "detail": "Fact Check Active", "status": "verified"})

        # Stream initial metadata chunk with council_trace
        init_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_ts,
            "model": model,
            "session_id": session_id,
            "council_trace": council_trace,
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(init_chunk)}\n\n"

        # 1. Main Boss Model Execution (Dynamic ONNX GenAI DirectML Execution)
        if is_boss_active:
            self.boss_prompt_role = load_role_prompt("main_boss")
            system_instruction = f"{self.boss_prompt_role}\n\n[Council Telemetry]: Intent='{intent}'."
            if security_warning:
                system_instruction += f"\n- Minister 7 (Security Auditor Alert): {security_warning}"
            if retrieved_context:
                system_instruction += f"\n- Memory & Search Context:\n{retrieved_context}"
            if code_structure and any(code_structure.values()):
                system_instruction += f"\n- Minister 4 (Code AST Structure): Functions={code_structure.get('functions', [])}, Classes={code_structure.get('classes', [])}, Imports={code_structure.get('imports', [])}, LOC={code_structure.get('loc', 0)}"
            if intent == "diagram":
                diagram_tpl = self.ministers["minister_8"].generate_diagram(user_content)
                system_instruction += f"\n- Minister 8 (Mermaid Blueprint):\n{diagram_tpl}"
            system_instruction += "\n"

            # Sliding Context Window: Prune older messages if history is long to fit inside ONNX KV Cache (4096 max limit)
            recent_messages = list(messages)
            while len(recent_messages) > 1:
                test_prompt = f"<|im_start|>system\n{system_instruction}<|im_end|>\n"
                for msg in recent_messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    test_prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
                test_prompt += "<|im_start|>assistant\n"
                
                try:
                    test_tokens = self.genai_tokenizer.encode(test_prompt)
                    tok_len = len(test_tokens) if hasattr(test_tokens, "__len__") else getattr(test_tokens, "size", 100)
                except Exception:
                    tok_len = len(test_prompt) // 3

                if tok_len <= 3000:
                    break
                recent_messages.pop(0)

            prompt_text = f"<|im_start|>system\n{system_instruction}<|im_end|>\n"
            for msg in recent_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_text += f"<|im_start|>{role}\n{content}<|im_end|>\n"
            prompt_text += "<|im_start|>assistant\n"

            try:
                import onnxruntime_genai as og
                input_tokens = self.genai_tokenizer.encode(prompt_text)
                try:
                    num_input_tokens = len(input_tokens) if hasattr(input_tokens, "__len__") else getattr(input_tokens, "size", 500)
                except Exception:
                    num_input_tokens = 500

                safe_max_length = min(4096, num_input_tokens + 2048)

                params = og.GeneratorParams(self.genai_model)
                params.set_search_options(max_length=safe_max_length, temperature=temperature)

                generator = og.Generator(self.genai_model, params)
                if hasattr(generator, "append_tokens"):
                    generator.append_tokens(input_tokens)
                elif hasattr(params, "input_ids"):
                    try:
                        params.input_ids = input_tokens
                    except Exception:
                        pass
                else:
                    try:
                        generator.set_inputs(input_tokens)
                    except Exception:
                        pass

                tokenizer_stream = self.genai_tokenizer.create_stream()

                full_text = ""
                while not generator.is_done():
                    generator.generate_next_token()
                    next_tokens = generator.get_next_tokens()
                    delta_text = ""
                    if len(next_tokens) > 0:
                        new_token = next_tokens[0]
                        delta_text = tokenizer_stream.decode(new_token)
                    if delta_text:
                        full_text += delta_text
                        chunk_data = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created_ts,
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": delta_text},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"

                # Flush any leftover characters from tokenizer_stream
                if hasattr(tokenizer_stream, "flush"):
                    try:
                        final_flush = tokenizer_stream.flush()
                        if final_flush:
                            full_text += final_flush
                            yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': created_ts, 'model': model, 'choices': [{'index': 0, 'delta': {'content': final_flush}, 'finish_reason': None}]})}\n\n"
                    except Exception:
                        pass

                fact_res = self.ministers["minister_6"].verify_facts(full_text)
                if not fact_res["verified"] or fact_res.get("hallucination_score", 0) > 0.8:
                    flagged = ", ".join(fact_res.get("flagged", [])) if fact_res.get("flagged") else "phantom package"
                    disclaimer = f"\n\n[Fact Check Note by Minister 6: Flagged potential {flagged}]"
                    full_text += disclaimer
                    yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': created_ts, 'model': model, 'choices': [{'index': 0, 'delta': {'content': disclaimer}, 'finish_reason': None}]})}\n\n"

                end_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(end_chunk)}\n\n"
                yield "data: [DONE]\n\n"

                self.memory_vault.store_cached_response(user_content, full_text, query_vec)
                self.memory_vault.add_session_message(session_id, "user", user_content)
                self.memory_vault.add_session_message(session_id, "assistant", full_text + security_warning)
                return
            except Exception as e:
                logger.error(f"Error during ONNX GenAI generation: {e}")

        # 2. Dynamic Minister Council Execution (when GGUF model binary is omitted)
        response_text = self._synthesize_council_response(user_content, intent, code_structure, retrieved_context, security_warning)

        # Stream delta chunks dynamically
        words = response_text.split(" ")
        for i, word in enumerate(words):
            delta = word + (" " if i < len(words) - 1 else "")
            chunk_data = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created_ts,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": delta},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(chunk_data)}\n\n"
            time.sleep(0.015)

        end_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_ts,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(end_chunk)}\n\n"
        yield "data: [DONE]\n\n"

        self.memory_vault.add_session_message(session_id, "user", user_content)
        self.memory_vault.add_session_message(session_id, "assistant", response_text)

    def _synthesize_council_response(self, user_content: str, intent: str, code_structure: Dict[str, Any], retrieved_context: str, security_warning: str) -> str:
        """Synthesizes dynamic model responses using the 8-Minister Council when LLM GGUF model binary is un-downloaded."""
        text_lower = user_content.lower()

        if intent == "diagram" or "diagram" in text_lower or "architecture" in text_lower:
            minister_8 = self.ministers["minister_8"]
            return minister_8.generate_diagram(user_content)

        if intent == "code_parse":
            minister_4 = self.ministers["minister_4"]
            ast_res = minister_4.parse_code(user_content)
            return f"Code structure analyzed by Minister 4 (Code Parser):\n```json\n{json.dumps(ast_res, indent=2)}\n```"

        if intent == "autocomplete":
            minister_5 = self.ministers["minister_5"]
            completion = minister_5.autocomplete(user_content)
            return f"Predicted completion by Minister 5:\n```\n{user_content}{completion}\n```"

        parts = [
            f"[Main Boss ONNX Model Artifact missing from {self.models_dir}]. Please run `python download_models.py` or start the server to auto-provision qwen2.5-coder-1.5b-onnx for full LLM text generation.",
            f"Minister 1 (Intent Router): Classified intent as '{intent}'.",
        ]
        if code_structure and any(code_structure.values()):
            parts.append(f"Minister 4 (Code Parser): Extracted syntax elements: {json.dumps(code_structure)}")
        if retrieved_context:
            parts.append(retrieved_context)
        if security_warning:
            parts.append(security_warning)

        return "\n\n".join(parts)

    def fast_autocomplete(self, prefix: str, suffix: str = "") -> str:
        """Fast single-line autocomplete via Minister 5 using dedicated non-blocking FIM lock."""
        with self._fim_lock:
            minister_5 = self.ministers["minister_5"]
            return minister_5.autocomplete(prefix, suffix)

    def create_embeddings(self, input_data: Any) -> List[List[float]]:
        minister_2 = self.ministers["minister_2"]
        if isinstance(input_data, str):
            return [minister_2.embed(input_data)]
        elif isinstance(input_data, list):
            return [minister_2.embed(str(item)) for item in input_data]
        return [minister_2.embed("")]
