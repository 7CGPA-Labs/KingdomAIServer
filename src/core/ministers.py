"""
Lean 2-Minister Council & Native Utilities Adapter for V2 Engine.
Wraps V2 Lean Council (Embedder, Re-Ranker) and Zero-VRAM Native Utilities while preserving backward compatibility.
"""
import os
import re
import math
import logging
import threading
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union

from src.utils import get_models_dir, load_role_prompt
from src.core.hardware import HardwareAccelerationEngine
from src.core.council import LeanCouncilManager
from src.rag.embedder import BGEEmbedder
from src.rag.retriever import BGEReranker
from src.processing.chunking import TreeSitterChunker
from src.processing.preprocessor import Preprocessor, ManifestLinter, VulnerabilityScanner, StructuralTrimmer

logger = logging.getLogger("kingdom.ministers")

class WorkspacePathJailError(PermissionError):
    """Exception raised when an indexing operation attempts to escape the active workspace boundary."""
    pass

class WorkspacePathJail:
    """Enforces strict path traversal boundary preventing RAG/AST parsers from accessing sensitive user directories."""
    
    FORBIDDEN_PATTERNS = [
        "\\.ssh",
        "\\.aws",
        "\\.git",
        "\\.gnupg",
        "\\appdata\\roaming",
        "c:\\windows",
        "c:\\program files",
        "c:\\program files (x86)",
    ]

    @classmethod
    def validate_path(cls, path_input: Union[str, Path], workspace_root: Optional[Union[str, Path]] = None) -> Path:
        target_path = Path(path_input).resolve()
        path_str_lower = str(target_path).lower()

        # Check against sensitive system/user directories
        for forbidden in cls.FORBIDDEN_PATTERNS:
            if forbidden in path_str_lower:
                raise WorkspacePathJailError(
                    f"Access Denied: Path '{target_path}' traverses sensitive user/system directory '{forbidden}'."
                )

        # If a workspace root is specified, enforce strict subtree containment
        if workspace_root:
            root_path = Path(workspace_root).resolve()
            try:
                target_path.relative_to(root_path)
            except ValueError:
                raise WorkspacePathJailError(
                    f"Access Denied: Path '{target_path}' escapes active workspace root '{root_path}'."
                )

        return target_path


class BaseMinister:
    """Base class for V2 Council Ministers and Native Utility Adapters."""

    def __init__(self, name: str, model_filename: str, hardware_engine: HardwareAccelerationEngine, models_dir: Optional[Path] = None, lazy_load: bool = True, role_id: str = ""):
        self.name = name
        self.model_filename = model_filename
        self.role_id = role_id
        self.prompt_role = load_role_prompt(role_id) if role_id else f"Role for {name} active."
        self.models_dir = Path(models_dir) if models_dir else get_models_dir()
        self.model_path = self.models_dir / model_filename
        self.hardware_engine = hardware_engine
        self.session = None
        self.provider, self.tier = self.hardware_engine.resolve_execution_provider()
        self._lock = threading.Lock()
        if not lazy_load:
            self._load_session()

    def _load_session(self):
        with self._lock:
            if self.session is not None:
                return
            if self.model_path.exists() and self.model_path.stat().st_size > 0:
                try:
                    import llama_cpp
                    self.session = "active"
                except Exception as e:
                    logger.debug(f"Optional GGUF session load for {self.name}: {e}")

    @property
    def is_model_loaded(self) -> bool:
        return self.session is not None or self.model_path.exists()


class MinisterFactory:
    """Factory for instantiating V2 Council Ministers and Native Utilities."""

    def __init__(self, hardware_engine: HardwareAccelerationEngine, models_dir: Optional[Path] = None):
        self.hardware_engine = hardware_engine
        self.models_dir = Path(models_dir) if models_dir else get_models_dir()

    def create_all_ministers(self) -> Dict[str, BaseMinister]:
        ministers = {}
        mapping = {
            1: ("Minister 1 (Workspace Embedder)", "bge-small-en-v1.5-q4_k_m.gguf"),
            2: ("Minister 2 (Context Re-Ranker)", "bge-reranker-base-q4_k_m.gguf")
        }
        for i in range(1, 3):
            name, filename = mapping[i]
            ministers[f"minister_{i}"] = BaseMinister(name, filename, self.hardware_engine, models_dir=self.models_dir, lazy_load=True, role_id=f"minister_{i}")
        return ministers
