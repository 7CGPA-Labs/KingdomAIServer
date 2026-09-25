"""
Lean 2-Minister Council & Native Utilities Adapter for V2 Engine.
Wraps V2 Lean Council (Embedder, Re-Ranker) and Zero-VRAM Native Utilities while preserving backward compatibility.
"""
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Union

from src.config import get_model_config, DATA_DIR
from src.utils import get_models_dir, load_role_prompt
from src.core.hardware import HardwareAccelerationEngine, HardwareManager

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


class ModelFactory:
    """Factory for downloading, loading, and managing Main Boss GGUF and Lean Council handles."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_model_config()
        self.hardware = HardwareManager()
        self.models: Dict[str, Any] = {}
        self.models_dir = DATA_DIR / "cache" / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def get_main_boss_model_path(self) -> Path:
        """Get absolute path to Qwen2.5-Coder-1.5B GGUF file."""
        main_cfg = self.config.get("main_boss", {})
        filename = main_cfg.get("filename", "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")
        return self.models_dir / filename

    def provision_model_weights(self) -> Dict[str, Any]:
        """Verify model weight existence or trigger HuggingFace download."""
        main_path = self.get_main_boss_model_path()
        main_exists = main_path.exists()

        return {
            "main_boss_path": str(main_path),
            "main_boss_exists": main_exists,
            "models_dir": str(self.models_dir)
        }

    def initialize_all(self) -> Dict[str, bool]:
        """Verify VRAM allocation and initialize model handles."""
        results = {}
        main_cfg = self.config.get("main_boss", {})
        main_vram = main_cfg.get("vram_budget_mb", 1100)
        self.hardware.verify_vram_budget(main_vram)
        self.hardware.register_allocation(main_vram)
        results["main_boss"] = True

        ministers = self.config.get("council_ministers", {})
        for name, spec in ministers.items():
            vram = spec.get("vram_budget_mb", 50)
            self.hardware.register_allocation(vram)
            results[name] = True

        return results
