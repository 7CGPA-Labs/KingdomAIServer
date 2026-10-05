"""
[DEPRECATED in V3] Legacy Rich Terminal CLI for Kingdom AI Server.
NOTE: In Kingdom AI Studio V3, the architecture is 100% on-device in-process
Slint Native Desktop GUI. All terminal UI capabilities (chat, model management,
telemetry, RAG indexing, security audits) have been superseded by the Slint GUI (main.py).
This module is maintained as a lightweight deprecation stub pointing to main.py.
"""
import sys
import time
import warnings
from typing import Optional
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    Console = None
    Panel = None
    Table = None
    Text = None

from src.core.local_llm import LlamaCppOrchestrator
from src.core.hardware import HardwareManager, STATIC_VRAM_CEILING_MB
from src.processing.cache import ResponseCacheDB
from src.prompts.templates import HeuristicIntentRouter
from src.rag.embedder import BGEEmbedder
from src.rag.retriever import BGEReranker


class KingdomCLI:
    """[DEPRECATED in V3] Lightweight backward-compatible stub for legacy Terminal CLI."""

    def __init__(self):
        warnings.warn(
            "KingdomCLI is deprecated and decommissioned in V3. "
            "Use Kingdom AI Studio V3 Slint Desktop GUI (main.py / src.gui.app_controller).",
            DeprecationWarning,
            stacklevel=2,
        )
        self.orchestrator = LlamaCppOrchestrator()
        self.hw_manager = HardwareManager()
        self.active_model_name = "qwen2.5-coder-1.5b"
        self.active_model_vram = 1100
        self.cache_db = ResponseCacheDB()
        self.router = HeuristicIntentRouter()
        self.embedder = BGEEmbedder()
        self.reranker = BGEReranker()
        self.chat_history = []
        self.total_cache_hits = 0
        self.total_queries = 0

    @property
    def current_vram_allocated_mb(self) -> int:
        """Calculate live resident VRAM allocation dynamically based on loaded model components."""
        total = 0
        if self.orchestrator and getattr(self.orchestrator, "is_loaded", False):
            total += self.active_model_vram
        if self.embedder and getattr(self.embedder, "is_model_loaded", False):
            total += 35
        if self.reranker and getattr(self.reranker, "is_model_loaded", False):
            total += 110
        if self.hw_manager:
            self.hw_manager.vram_allocated_mb = total
        return total

    def show_models(self):
        """Display model list (stub for deprecated CLI)."""
        from src.utils.verifier import MODEL_MANIFEST, UPGRADE_MODELS
        from src.utils import get_models_dir

        models_dir = get_models_dir()
        if Console and Table:
            console = Console()
            table = Table(title="🤖 Model Registry & Upgrades [DEPRECATED CLI STUB]")
            table.add_column("Identifier", style="bold cyan")
            table.add_column("Model Name", style="white")
            table.add_column("Status", style="bold")

            table.add_row("qwen2.5-coder-1.5b", "Qwen2.5-Coder-1.5B (Default Boss)", "Available")
            for key, spec in UPGRADE_MODELS.items():
                target_file = models_dir / spec.get("filename", "")
                status = "Installed" if target_file.exists() else "Available"
                table.add_row(key, spec.get("name", key), status)
            console.print(table)
        else:
            print("[Models] qwen2.5-coder-1.5b (Default Boss)")

    def switch_model_cli(self, model_query: str):
        """Hot-swap active LLM weights in-process without restarting server."""
        from src.utils.verifier import get_upgrade_model_spec
        from src.utils import get_models_dir

        models_dir = get_models_dir()
        spec = get_upgrade_model_spec(model_query)

        if spec:
            target_filename = spec["filename"]
            target_name = spec["id"]
            target_vram = spec["vram_required_mb"]
        elif model_query.lower() in ("default", "1.5b", "qwen2.5-coder-1.5b"):
            target_filename = "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
            target_name = "qwen2.5-coder-1.5b"
            target_vram = 1100
        else:
            target_filename = f"{model_query}.gguf"
            target_name = model_query
            target_vram = 2000

        target_path = models_dir / target_filename
        if not target_path.exists():
            print(f"[Warning] Model file '{target_filename}' is not downloaded yet.")
            return

        vram_diff = target_vram - self.active_model_vram
        projected_vram = self.current_vram_allocated_mb + vram_diff
        if projected_vram > STATIC_VRAM_CEILING_MB:
            print(f"[Error] Cannot switch: requires {target_vram} MB VRAM, exceeding ceiling.")
            return

        success = self.orchestrator.switch_model(str(target_path), model_name=target_name)
        if success or target_path.exists():
            self.active_model_name = target_name
            self.active_model_vram = target_vram
            if self.hw_manager:
                self.hw_manager.vram_allocated_mb = self.current_vram_allocated_mb

    def show_health(self):
        """Display hardware telemetry (stub)."""
        print(f"[Health] Active Model: {self.active_model_name} | VRAM: {self.current_vram_allocated_mb} MB")

    def show_cache_stats(self):
        """Display cache stats (stub)."""
        stats = self.cache_db.get_stats()
        print(f"[Cache Stats] Entries: {stats.get('total_cached_entries', 0)}")

    def show_top_monitor(self):
        """Deprecated monitor launcher."""
        from src.cli.server_dashboard import main as dashboard_main
        dashboard_main()

    def process_chat(self, user_input: str) -> Optional[str]:
        """Process chat (stub)."""
        self.total_queries += 1
        res = self.orchestrator.generate_completion(user_input, max_tokens=128)
        return res.get("text", "")

    def run(self):
        """Deprecated interactive REPL loop - redirects to Slint GUI."""
        main()


def main():
    """Legacy CLI entry point - notifies deprecation and launches Slint Desktop Studio."""
    warnings.warn(
        "Kingdom AI Terminal CLI is deprecated and decommissioned in V3. "
        "Redirecting to Kingdom AI Studio V3 Slint Native Desktop GUI (main.py).",
        DeprecationWarning,
        stacklevel=2,
    )
    print("======================================================================")
    print(" ⚠️  NOTICE: Kingdom AI Terminal CLI (TUI) is DECOMMISSIONED in V3.")
    print(" All features (chat, models hub, telemetry, RAG, security audits)")
    print(" are now available in Kingdom AI Studio V3 Slint Native Desktop GUI.")
    print(" Redirecting to Kingdom AI Studio V3 (main.py)...")
    print("======================================================================")
    try:
        from main import launch_studio
        launch_studio()
    except Exception as exc:
        print(f"To launch the V3 Desktop GUI, run: python main.py ({exc})")


if __name__ == "__main__":
    main()
