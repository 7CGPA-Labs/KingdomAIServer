"""
Kingdom Orchestrator V2 Adapter.
Coordinating Main Boss GGUF (Qwen2.5-Coder-1.5B) & Lean 3-Minister Council.
"""
import time
import json
import logging
import threading
from pathlib import Path
from typing import AsyncGenerator, List, Dict, Any, Optional

from src.core.hardware import HardwareAccelerationEngine
from src.core.ministers import MinisterFactory, BaseMinister
from src.utils import get_models_dir, load_role_prompt
from src.core.local_llm import LlamaCppOrchestrator
from src.core.council import LeanCouncilManager
from src.prompts.templates import HeuristicIntentRouter

logger = logging.getLogger("kingdom.orchestrator")

class KingdomOrchestrator:
    """Master Orchestrator for Kingdom AI Server V2 (llama.cpp GGUF Engine)."""

    def __init__(self, models_dir: Optional[Any] = None, db_path: Optional[Any] = None, preload_in_background: bool = False):
        self.models_dir = Path(models_dir) if models_dir else get_models_dir()
        self.hardware_engine = HardwareAccelerationEngine()
        self.minister_factory = MinisterFactory(self.hardware_engine, self.models_dir)
        self.ministers = self.minister_factory.create_all_ministers()
        self.boss_prompt_role = load_role_prompt("main_boss")
        self.council_manager = LeanCouncilManager(db_path=db_path or "data/vectordb/cognitive_vault.db")
        self.local_llm = LlamaCppOrchestrator()
        self.router = HeuristicIntentRouter()
        self._boss_lock = threading.Lock()

    def _init_boss_llm(self):
        with self._boss_lock:
            model_path = self.models_dir / "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
            if model_path.exists():
                self.local_llm.model_path = str(model_path)
                self.local_llm.load_model()

    @property
    def is_boss_loaded(self) -> bool:
        return self.local_llm.is_loaded

    def get_model_status(self) -> Dict[str, bool]:
        status = {"boss_qwen2.5": self.is_boss_loaded}
        for k, m in self.ministers.items():
            status[m.model_filename] = m.is_model_loaded
        return status

    def route_request(self, user_prompt: str) -> str:
        res = self.router.route_intent(user_prompt)
        return res["intent"]
