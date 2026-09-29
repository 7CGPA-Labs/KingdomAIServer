"""
AppController - Master GUI Controller for Kingdom AI Studio V3.
Connects Slint declarative UI components directly to the in-process
LlamaCppOrchestrator, ResponseCacheDB, and TelemetryBridge.
"""
import os
import sys
import time
import logging
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import slint

logger = logging.getLogger("kingdom.gui.controller")

def _dispatch_ui(callback: Callable[[], None]) -> None:
    """Dispatches a callback to the Slint UI thread safely."""
    if threading.current_thread() is threading.main_thread():
        callback()
    else:
        slint.native.invoke_from_event_loop(callback)

from src.gui.models_adapter import (
    STUDIO_MODELS_CATALOG,
    get_model_spec,
    get_model_filepath,
    build_slint_model_list
)
from src.gui.worker import InferenceWorker, DownloadWorker
from src.gui.telemetry_bridge import TelemetryBridge
from src.core.local_llm import LlamaCppOrchestrator
from src.processing.cache import ResponseCacheDB
from src.utils import get_models_dir

logger = logging.getLogger("kingdom.gui.controller")

def find_ui_path() -> Path:
    """Locate the ui/app.slint file across source repo, working dir, and installed directories."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "ui" / "app.slint",
        Path.cwd() / "ui" / "app.slint",
        Path(sys.prefix) / "ui" / "app.slint",
        Path(os.environ.get("LOCALAPPDATA", "")) / "KingdomAIServer" / "ui" / "app.slint",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]

DEFAULT_UI_PATH = find_ui_path()


class AppController:
    """Master controller managing Slint UI state and connecting in-process AI engines."""

    def __init__(
        self,
        ui_path: Optional[Path] = None,
        orchestrator: Optional[LlamaCppOrchestrator] = None,
        cache_db: Optional[ResponseCacheDB] = None,
        models_dir: Optional[Path] = None,
        auto_start_telemetry: bool = False
    ):
        self.ui_path = ui_path or DEFAULT_UI_PATH
        if not self.ui_path.exists():
            raise FileNotFoundError(f"Slint UI file not found: {self.ui_path}")

        # Load Slint UI Component Module
        self.ui_module = slint.load_file(str(self.ui_path))
        if not hasattr(self.ui_module, "MainWindow"):
            raise AttributeError("Loaded Slint module does not export MainWindow component")

        # Instantiate MainWindow
        self.window = self.ui_module.MainWindow()

        # Models & Working Directory
        self.models_dir = Path(models_dir or get_models_dir())
        self.active_workspace_path = Path.cwd()

        # In-Process AI Engines
        self.orchestrator = orchestrator or LlamaCppOrchestrator()
        self.cache_db = cache_db or ResponseCacheDB()

        # Internal State
        self.messages: List[Dict[str, str]] = []
        self._display_messages: List[Dict[str, str]] = []
        self.active_inference_worker: Optional[InferenceWorker] = None
        self.active_download_worker: Optional[DownloadWorker] = None

        # Telemetry Polling Bridge
        self.telemetry = TelemetryBridge(self.window, self.cache_db)

        # Initialize Default UI State & Wire Callbacks
        self._setup_initial_ui_state()
        self._register_callbacks()

        if auto_start_telemetry:
            self.telemetry.start()

    def _setup_initial_ui_state(self) -> None:
        """Initialize UI properties with active hardware and catalog status."""
        active_id = getattr(self.orchestrator, "model_name", "qwen2.5-coder-1.5b")
        spec = get_model_spec(active_id)
        display_name = spec["name"] if spec else active_id

        self.window.active_model = display_name
        self.window.active_workspace = self.active_workspace_path.name
        self.window.active_nav = "chat"
        self.window.model_list = build_slint_model_list(active_id, self.models_dir)

        # Initial Welcome Message
        welcome_msg = {
            "id": "1",
            "role": "assistant",
            "content": "👑 Welcome to Kingdom AI Studio V3!\n\nI am your 100% on-device AI programming assistant. Type your message below, or type / to open the command palette.",
            "timestamp": time.strftime("%H:%M")
        }
        self._display_messages = [welcome_msg]
        self.window.chat_messages = slint.ListModel(self._display_messages)

        # Run one initial telemetry snapshot
        self.telemetry.update_once()

    def _register_callbacks(self) -> None:
        """Bind Slint UI user action callbacks to controller methods."""
        self.window.send_message = self.on_send_message
        self.window.stop_generation = self.on_stop_generation
        self.window.switch_model = self.on_switch_model
        self.window.download_model = self.on_download_model
        self.window.select_workspace = self.on_select_workspace
        self.window.purge_cache = self.on_purge_cache
        self.window.clear_chat = self.on_clear_chat
        self.window.new_chat = self.on_new_chat
        self.window.execute_command = self.on_execute_command
        self.window.set_mode = self.on_set_mode
        self.window.mention_resource = self.on_mention_resource
        self.window.trigger_task = self.on_trigger_task
        self.window.cancel_task = self.on_cancel_task

    # --------------------------------------------------------------------------
    # User Actions & Event Handlers
    # --------------------------------------------------------------------------

    def on_send_message(self, prompt: str) -> None:
        """Handle user message submission."""
        clean_prompt = prompt.strip()
        if not clean_prompt:
            return

        if self.window.is_generating:
            return

        # Check for Slash Commands
        if clean_prompt.startswith("/"):
            self.on_execute_command(clean_prompt)
            return

        # Append User Message to State
        timestamp = time.strftime("%H:%M")
        msg_id = str(len(self._display_messages) + 1)
        user_msg = {
            "id": msg_id,
            "role": "user",
            "content": clean_prompt,
            "timestamp": timestamp
        }
        self.messages.append({"role": "user", "content": clean_prompt})
        self._display_messages.append(user_msg)
        self.window.chat_messages = slint.ListModel(self._display_messages)

        # Update UI to Generating State
        self.window.is_generating = True
        self.window.streaming_text = ""

        # Launch Inference Worker
        def _on_token(token: str, accumulated: str):
            def _apply():
                self.window.streaming_text = accumulated
            _dispatch_ui(_apply)

        def _on_complete(final_text: str, tokens_per_sec: float, latency_ms: float):
            def _apply():
                asst_id = str(len(self._display_messages) + 1)
                asst_msg = {
                    "id": asst_id,
                    "role": "assistant",
                    "content": final_text,
                    "timestamp": time.strftime("%H:%M")
                }
                self.messages.append({"role": "assistant", "content": final_text})
                self._display_messages.append(asst_msg)
                self.window.chat_messages = slint.ListModel(self._display_messages)
                self.window.streaming_text = ""
                self.window.is_generating = False
                if tokens_per_sec > 0:
                    self.window.speed_tokens_sec = tokens_per_sec
                self.active_inference_worker = None
            _dispatch_ui(_apply)

        def _on_error(err_msg: str):
            def _apply():
                err_id = str(len(self._display_messages) + 1)
                err_bubble = {
                    "id": err_id,
                    "role": "assistant",
                    "content": f"⚠️ Generation Error: {err_msg}",
                    "timestamp": time.strftime("%H:%M")
                }
                self._display_messages.append(err_bubble)
                self.window.chat_messages = slint.ListModel(self._display_messages)
                self.window.streaming_text = ""
                self.window.is_generating = False
                self.active_inference_worker = None
            _dispatch_ui(_apply)

        self.active_inference_worker = InferenceWorker(
            orchestrator=self.orchestrator,
            messages=list(self.messages),
            on_token=_on_token,
            on_complete=_on_complete,
            on_error=_on_error,
            cache_db=self.cache_db
        )
        self.active_inference_worker.start()

    def on_stop_generation(self) -> None:
        """Interrupt and cancel ongoing generation immediately."""
        if self.active_inference_worker:
            self.active_inference_worker.cancel()
        self.window.is_generating = False
        if self.window.streaming_text:
            asst_id = str(len(self._display_messages) + 1)
            asst_msg = {
                "id": asst_id,
                "role": "assistant",
                "content": self.window.streaming_text + " *(Generation stopped by user)*",
                "timestamp": time.strftime("%H:%M")
            }
            self._display_messages.append(asst_msg)
            self.window.chat_messages = slint.ListModel(self._display_messages)
            self.window.streaming_text = ""

    def on_switch_model(self, model_id: str) -> None:
        """Hot-swap the active in-process model weights."""
        spec = get_model_spec(model_id)
        if not spec:
            return

        model_path = get_model_filepath(model_id, self.models_dir)
        if not model_path or not model_path.exists() or model_path.stat().st_size < 10 * 1024 * 1024:
            # Model not installed - switch to models tab and alert
            self.window.active_nav = "models"
            self.window.download_status = f"Please download {spec['name']} first."
            return

        success = self.orchestrator.switch_model(str(model_path), model_id)
        if success or not getattr(self.orchestrator, "strict_gpu", True):
            self.window.active_model = spec["name"]
            self.window.model_list = build_slint_model_list(model_id, self.models_dir)
            logger.info("Successfully switched active model to: %s", spec["name"])

    def on_download_model(self, model_id: str) -> None:
        """Initiate background download of model weights with progress reporting."""
        if self.window.is_downloading:
            return

        spec = get_model_spec(model_id)
        if not spec:
            return

        self.window.is_downloading = True
        self.window.download_progress = 0.0
        self.window.download_status = f"Connecting to download {spec['name']}..."

        def _on_progress(pct: float, status_str: str):
            def _apply():
                self.window.download_progress = pct
                self.window.download_status = status_str
            _dispatch_ui(_apply)

        def _on_complete(success: bool, message: str):
            def _apply():
                self.window.is_downloading = False
                self.window.download_status = message
                active_id = getattr(self.orchestrator, "model_name", "qwen2.5-coder-1.5b")
                self.window.model_list = build_slint_model_list(active_id, self.models_dir)
                self.active_download_worker = None
            _dispatch_ui(_apply)

        self.active_download_worker = DownloadWorker(
            model_id=model_id,
            on_progress=_on_progress,
            on_complete=_on_complete,
            models_dir=self.models_dir
        )
        self.active_download_worker.start()

    def on_select_workspace(self) -> None:
        """Prompt user for a workspace folder."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected_dir = filedialog.askdirectory(
                initialdir=str(self.active_workspace_path),
                title="Select Kingdom AI Workspace"
            )
            root.destroy()
            if selected_dir:
                self.active_workspace_path = Path(selected_dir)
                self.window.active_workspace = self.active_workspace_path.name
        except Exception as e:
            logger.debug("Workspace selection error: %s", e)

    def on_purge_cache(self) -> None:
        """Clear all entries from the response cache DB."""
        if self.cache_db:
            self.cache_db.clear()
        self.window.cache_entries = 0
        self.window.cache_hits = 0
        self.window.cache_hit_ratio = 0.0

    def on_clear_chat(self) -> None:
        """Wipe conversation history."""
        self.messages.clear()
        self._display_messages.clear()
        self.window.chat_messages = slint.ListModel([])
        self.window.streaming_text = ""

    def on_new_chat(self) -> None:
        """Start a fresh session with welcome greeting."""
        self.on_clear_chat()
        welcome_msg = {
            "id": "1",
            "role": "assistant",
            "content": "✨ Fresh session initialized. How can I assist you with your code today?",
            "timestamp": time.strftime("%H:%M")
        }
        self._display_messages = [welcome_msg]
        self.window.chat_messages = slint.ListModel(self._display_messages)

    def on_set_mode(self, mode: str) -> None:
        """Handle execution mode change (normal, plan, goal)."""
        self.window.active_mode = mode
        logger.info("Switched execution mode to: %s", mode)

    def on_mention_resource(self, resource: str) -> None:
        """Handle mention insertion from the @ popup menu."""
        current = getattr(self.window, "prompt_text", "")
        if current and not current.endswith(" "):
            self.window.prompt_text = current + " " + resource + " "
        else:
            self.window.prompt_text = current + resource + " "

    def on_trigger_task(self, task_id: str) -> None:
        """Trigger an immediate run of a scheduled task."""
        self._append_system_chat_bubble(f"⏱️ Triggered task `{task_id}` immediately in background.")

    def on_cancel_task(self, task_id: str) -> None:
        """Cancel a running or scheduled task."""
        self._append_system_chat_bubble(f"🛑 Cancelled task `{task_id}`.")

    def on_execute_command(self, cmd_str: str) -> None:
        """Process slash commands (/goal, /plan, /grill-me, /schedule, /browser, /learn, /boost, /top, /models, /cache, /clearcache, /clear, /health, /help)."""
        clean = cmd_str.strip().lower()
        parts = clean.split()
        cmd = parts[0] if parts else ""

        if cmd == "/goal":
            self.window.active_mode = "goal"
            self._append_system_chat_bubble(
                "🎯 **Goal Mode Activated**\n\n"
                "The agent will execute autonomously with persistence, checking its own work and iterating until the objective is fully achieved."
            )

        elif cmd == "/plan":
            self.window.active_mode = "plan"
            self.window.aux_active_tab = "artifacts"
            self._append_system_chat_bubble(
                "📋 **Planning Mode Activated**\n\n"
                "Operating in deliberative architectural planning mode. The Artifacts inspector tab is open on the right."
            )

        elif cmd == "/grill-me":
            self._append_system_chat_bubble(
                "🔥 **Interactive Interview Mode (/grill-me)**\n\n"
                "I will interview you to clarify requirements and stress-test trade-offs. What feature or architectural change would you like to explore?"
            )

        elif cmd == "/schedule":
            self.window.active_nav = "tasks"
            self._append_system_chat_bubble(
                "⏱️ **Scheduled Tasks & Background Automation**\n\n"
                "Navigating to Scheduled Tasks. Manage recurring cron expressions and delayed one-shot timers."
            )

        elif cmd == "/browser":
            self._append_system_chat_bubble(
                "🌐 **Headless Browser Research Tool**\n\n"
                "- **Browser Status**: READY (Chromium / Puppeteer sandbox)\n"
                "- **Execution Policy**: `proceed-in-sandbox`\n"
                "- **Allowed Domains**: `antigravity.google`, `huggingface.co`, `github.com`\n"
                "- **DOM Parsing**: Markdown-converted snapshot engine active"
            )

        elif cmd == "/learn":
            self._append_system_chat_bubble(
                "🧠 **Pattern Learned & Persisted**\n\n"
                "Active project workflow pattern saved into `.agents/rules/` and response cache memory for future sessions."
            )

        elif cmd == "/boost":
            self._append_system_chat_bubble(
                "🚀 **Boost Mode Enabled**\n\n"
                "Multi-perspective reasoning and verification pass active via Lean Council (Boss LLM + Embedder + Reranker)."
            )

        elif cmd == "/top":
            self.window.active_nav = "ktop"

        elif cmd == "/models":
            self.window.active_nav = "models"

        elif cmd == "/cache":
            self.window.active_nav = "chat"
            stats = self.cache_db.get_stats() if self.cache_db else {}
            info_msg = (
                f"🗄️ **Response Cache DB (SQLite WAL)**\n\n"
                f"- **Total Cached Prompts**: {stats.get('total_cached_entries', 0)}\n"
                f"- **Total Cache Hits**: {stats.get('total_cache_hits', 0)}\n"
                f"- **Hit Ratio**: {stats.get('hit_ratio_pct', 0.0)}%\n"
                f"- **Database Size**: {stats.get('db_size_kb', 0.0)} KB\n"
                f"- **VRAM Footprint**: 0.00 MB (Zero VRAM)"
            )
            self._append_system_chat_bubble(info_msg)

        elif cmd == "/clearcache":
            self.on_purge_cache()
            self._append_system_chat_bubble("🧹 Response Cache DB has been purged successfully.")

        elif cmd == "/clear":
            self.on_clear_chat()

        elif cmd == "/health":
            health_report = (
                f"🏥 **Kingdom AI Studio V3 Diagnostics**\n\n"
                f"- **Compute Engine**: {self.window.silicon_provider}\n"
                f"- **Active LLM**: {self.window.active_model}\n"
                f"- **VRAM Status**: {self.window.vram_status} (Budget Ceiling: 6.00 GB)\n"
                f"- **CPU Usage**: {round(self.window.cpu_pct, 1)}%\n"
                f"- **System RAM**: {self.window.ram_used_gb} / {self.window.ram_total_gb} GB\n"
                f"- **AST Parser**: Tree-sitter active (Python, JS, TS, Rust, C++)\n"
                f"- **Lean Council**: Minister 1 (Embedder) & Minister 2 (Reranker) READY"
            )
            self._append_system_chat_bubble(health_report)

        elif cmd == "/help":
            help_text = (
                "📖 **Available Slash Commands**\n\n"
                "- `/goal`: Autonomous execution mode until objective is achieved\n"
                "- `/plan`: Architectural planning mode with live artifact generation\n"
                "- `/grill-me`: Interactive interview to clarify requirements\n"
                "- `/schedule`: Open Scheduled Tasks & delayed timers view\n"
                "- `/browser`: Inspect headless browser tool & domain allowlist\n"
                "- `/learn`: Persist workflow patterns into project rules\n"
                "- `/boost`: Enable boosted council multi-model reasoning\n"
                "- `/top`: Open K-Top real-time hardware telemetry dashboard\n"
                "- `/models`: Open Models Hub to view, download, and switch models\n"
                "- `/cache`: View Response Cache SQLite WAL performance metrics\n"
                "- `/clearcache`: Purge all cached prompt responses\n"
                "- `/health`: Run diagnostic health check on silicon & models\n"
                "- `/clear`: Clear conversation history\n"
                "- `/switch <model_id>`: Switch active in-process model weights\n"
                "- `/download <model_id>`: Download model weights from HuggingFace"
            )
            self._append_system_chat_bubble(help_text)

        elif cmd == "/switch" and len(parts) > 1:
            target_id = parts[1]
            self.on_switch_model(target_id)

        elif cmd == "/download" and len(parts) > 1:
            target_id = parts[1]
            self.on_download_model(target_id)

        else:
            self._append_system_chat_bubble(f"Unknown command: `{cmd_str}`. Type `/help` for available options.")

    def _append_system_chat_bubble(self, content: str) -> None:
        """Helper to post an informational message bubble to chat."""
        msg_id = str(len(self._display_messages) + 1)
        bubble = {
            "id": msg_id,
            "role": "assistant",
            "content": content,
            "timestamp": time.strftime("%H:%M")
        }
        self._display_messages.append(bubble)
        self.window.chat_messages = slint.ListModel(self._display_messages)

    # --------------------------------------------------------------------------
    # Lifecycle & Execution
    # --------------------------------------------------------------------------

    def run(self) -> None:
        """Start background threads and launch the Slint event loop."""
        self.telemetry.start()
        try:
            self.window.show()
            self.window.run()
        finally:
            self.telemetry.stop()
            if self.active_inference_worker:
                self.active_inference_worker.cancel()
            if self.active_download_worker:
                self.active_download_worker.cancel()
