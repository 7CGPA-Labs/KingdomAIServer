"""
The Kingdom Orchestrator: Master Boss (Qwen2.5-Coder-1.5B-Instruct) + 8-Minister Council router & inference manager.
Zero ready-made / zero mock policy: All responses are processed and generated dynamically by the active models.
"""
import time
import json
import uuid
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
from kingdom_server.core.hardware import HardwareAccelerationEngine
from kingdom_server.core.ministers import MinisterFactory, BaseMinister
from kingdom_server.core.memory_vault import MemoryVault
from kingdom_server.utils import get_models_dir

import threading

logger = logging.getLogger("kingdom.orchestrator")

class KingdomOrchestrator:
    """Master Orchestrator coordinating Master Boss (Qwen2.5-Coder ONNX) and 8 ONNX Ministers."""

    def __init__(self, models_dir: Optional[Any] = None, db_path: Optional[Any] = None, preload_in_background: bool = False):
        self.models_dir = models_dir or get_models_dir()
        self.hardware_engine = HardwareAccelerationEngine()
        self.minister_factory = MinisterFactory(self.hardware_engine, self.models_dir)
        self.ministers = self.minister_factory.create_all_ministers()
        self.memory_vault = MemoryVault(db_path=db_path)
        self.genai_model = None
        self.genai_tokenizer = None
        self._boss_lock = threading.Lock()
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
            if self._boss_initialized:
                return
            self._boss_initialized = True
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

        user_content = messages[-1].get("content", "") if messages else ""

        # Minister 1: Intent Classification (ONNX Runtime)
        intent = self.route_request(user_content)
        
        # Minister 7: Security Vulnerability Audit
        audit_res = self.audit_security(user_content)
        security_warning = ""
        if not audit_res["safe"]:
            warning_details = ", ".join([v["detail"] for v in audit_res["vulnerabilities"]])
            security_warning = f"\n\n[Security Alert by Minister 7]: Potential vulnerabilities detected ({warning_details})."

        # Minister 2 & Minister 3: Dense Semantic Vector Embedding & RAG Re-Ranking
        query_vec = self.get_context_embeddings(user_content)
        vector_matches = self.memory_vault.search_similar(query_vec, k=3)
        retrieved_context = ""
        if vector_matches:
            docs = [m["document"] for m in vector_matches if m["score"] > 0.3]
            ranked_docs = self.ministers["minister_3"].rerank(user_content, docs)
            if ranked_docs:
                retrieved_context = "\n\n[Cognitive Memory Context by Minister 3 Re-Ranker]:\n" + "\n".join([doc[0] for doc in ranked_docs])

        # Minister 4: Code AST Parsing
        code_structure = self.ministers["minister_4"].parse_code(user_content)

        # 1. Main Boss Model Execution (Dynamic ONNX GenAI DirectML Execution)
        self._init_boss_llm()
        if self.genai_model is not None and self.genai_tokenizer is not None:
            system_instruction = (
                "You are Kingdom AI (Main Boss: Qwen2.5-Coder), an expert software engineering assistant. "
                f"Minister 1 (Intent Router) classified request intent as '{intent}'."
            )
            if retrieved_context:
                system_instruction += f"{retrieved_context}\n"

            prompt_text = f"<|im_start|>system\n{system_instruction}<|im_end|>\n"
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_text += f"<|im_start|>{role}\n{content}<|im_end|>\n"
            prompt_text += "<|im_start|>assistant\n"

            try:
                import onnxruntime_genai as og
                params = og.GeneratorParams(self.genai_model)
                params.set_search_options(max_length=4096, temperature=temperature)
                input_tokens = self.genai_tokenizer.encode(prompt_text)
                params.input_ids = input_tokens

                generator = og.Generator(self.genai_model, params)
                tokenizer_stream = self.genai_tokenizer.create_stream()

                full_text = ""
                while not generator.is_done():
                    generator.generate_next_token()
                    new_token = generator.get_next_tokens()[0]
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

                fact_res = self.ministers["minister_6"].verify_facts(full_text)
                if not fact_res["verified"]:
                    full_text += "\n\n[Fact Check Warning by Minister 6]: Potential unverified patterns detected."

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
            f"[Main Boss GGUF Model Artifact missing from {self.models_dir}]. Please run `kingdom download` to auto-provision qwen2.5-coder-1.5b-instruct-q4_k_m.gguf for full LLM text generation.",
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
        minister_5 = self.ministers["minister_5"]
        return minister_5.autocomplete(prefix, suffix)

    def create_embeddings(self, input_data: Any) -> List[List[float]]:
        minister_2 = self.ministers["minister_2"]
        if isinstance(input_data, str):
            return [minister_2.embed(input_data)]
        elif isinstance(input_data, list):
            return [minister_2.embed(str(item)) for item in input_data]
        return [minister_2.embed("")]
