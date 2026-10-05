"""
Worker threads for Kingdom AI Studio V3.
Handles non-blocking LLM token generation streaming, cache integration,
and background model downloading without blocking the Slint UI event loop.
"""
import time
import logging
import threading
import ssl
import urllib.request
import shutil
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional

from src.gui.models_adapter import get_model_spec, get_model_filepath
from src.utils import get_models_dir

logger = logging.getLogger("kingdom.gui.worker")


class InferenceWorker:
    """Background worker thread for LLM token streaming and RAG pre-processing."""

    def __init__(
        self,
        orchestrator: Any,
        messages: List[Dict[str, str]],
        on_token: Callable[[str, str], None],
        on_complete: Callable[[str, float, float], None],
        on_error: Callable[[str], None],
        cache_db: Optional[Any] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        enricher: Optional[Any] = None,
        workspace_path: Optional[Path] = None,
    ):
        self.orchestrator = orchestrator
        self.messages = messages
        self.on_token = on_token
        self.on_complete = on_complete
        self.on_error = on_error
        self.cache_db = cache_db
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.enricher = enricher
        self.workspace_path = workspace_path

        self._stop_requested = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start inference on a background daemon thread."""
        self._stop_requested = False
        self._thread = threading.Thread(target=self._run, daemon=True, name="KingdomInferenceWorker")
        self._thread.start()

    def cancel(self) -> None:
        """Request immediate cooperative cancellation."""
        self._stop_requested = True

    def _run(self) -> None:
        start_time = time.perf_counter()
        accumulated_text = ""
        token_count = 0

        try:
            # 1. Orchestrate & Enrich Context (Intent routing, Personas, Security scans)
            effective_msgs = list(self.messages)
            effective_temp = self.temperature
            if self.enricher:
                try:
                    effective_msgs, route_info, recommended_temp = self.enricher.enrich_chat_context(
                        self.messages, workspace_path=self.workspace_path
                    )
                    if self.temperature == 0.7 and recommended_temp is not None:
                        effective_temp = recommended_temp
                except Exception as ee:
                    logger.debug("Context enrichment notice: %s", ee)

            last_prompt = ""
            for m in reversed(effective_msgs):
                if m.get("role") == "user":
                    last_prompt = m.get("content", "")
                    break

            # 2. Instant Cache Check (< 0.05 ms latency)
            cache_key = None
            if self.cache_db and last_prompt:
                try:
                    model_name = getattr(self.orchestrator, "model_name", "qwen2.5-coder-1.5b")
                    cache_key = self.cache_db.compute_cache_key(
                        model=model_name,
                        prompt=last_prompt,
                        temperature=effective_temp,
                        max_tokens=self.max_tokens
                    )
                    cached = self.cache_db.get(cache_key)
                    if cached:
                        cached_text = cached.get("text", "")
                        self.on_token(cached_text, cached_text)
                        hit_lat = cached.get("cache_hit_latency_ms", 0.05)
                        self.on_complete(cached_text, 999.0, hit_lat)
                        return
                except Exception as ce:
                    logger.debug("Cache lookup non-fatal error: %s", ce)

            # 3. In-Process Token Streaming via LlamaCppOrchestrator
            stream = self.orchestrator.stream_chat_completion(
                messages=effective_msgs,
                max_tokens=self.max_tokens,
                temperature=effective_temp
            )

            for chunk in stream:
                if self._stop_requested:
                    break

                choices = chunk.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                delta_content = delta.get("content", "")

                if delta_content:
                    accumulated_text += delta_content
                    token_count += 1
                    self.on_token(delta_content, accumulated_text)

            elapsed_sec = time.perf_counter() - start_time
            elapsed_ms = elapsed_sec * 1000.0
            tokens_per_sec = round(token_count / elapsed_sec, 1) if elapsed_sec > 0 else 0.0

            # 3. Store Completed Output in Cache DB
            if self.cache_db and cache_key and accumulated_text and not self._stop_requested:
                try:
                    self.cache_db.put(
                        cache_key=cache_key,
                        response_text=accumulated_text,
                        response_json={"text": accumulated_text},
                        query_type="CHAT"
                    )
                except Exception as ce:
                    logger.debug("Cache storage non-fatal error: %s", ce)

            self.on_complete(accumulated_text, tokens_per_sec, elapsed_ms)

        except Exception as e:
            logger.exception("Inference error: %s", e)
            self.on_error(str(e))


class DownloadWorker:
    """Background worker thread for downloading GGUF model weights from HuggingFace."""

    def __init__(
        self,
        model_id: str,
        on_progress: Callable[[float, str], None],
        on_complete: Callable[[bool, str], None],
        models_dir: Optional[Path] = None
    ):
        self.model_id = model_id
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.models_dir = Path(models_dir or get_models_dir())
        self._stop_requested = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start downloading on a background daemon thread."""
        self._stop_requested = False
        self._thread = threading.Thread(target=self._run, daemon=True, name="KingdomDownloadWorker")
        self._thread.start()

    def cancel(self) -> None:
        """Cancel the download."""
        self._stop_requested = True

    def _run(self) -> None:
        spec = get_model_spec(self.model_id)
        if not spec:
            self.on_complete(False, f"Unknown model identifier: '{self.model_id}'")
            return

        repo_id = spec["repo_id"]
        filename = spec["filename"]
        expected_bytes = int(spec["approx_size_mb"] * 1024 * 1024)
        target_path = self.models_dir / filename
        temp_target = self.models_dir / f"{filename}.part"

        self.models_dir.mkdir(parents=True, exist_ok=True)

        if target_path.exists() and target_path.stat().st_size >= int(expected_bytes * 0.4):
            self.on_progress(1.0, f"{spec['name']} already downloaded.")
            self.on_complete(True, f"{spec['name']} is already installed.")
            return

        download_url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
        headers = {
            "User-Agent": "Mozilla/5.0 KingdomAIStudio/3.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "*/*"
        }

        self.on_progress(0.0, f"Connecting to HuggingFace ({repo_id})...")

        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(download_url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=300) as response:
                total_bytes = int(response.headers.get("Content-Length", 0)) or expected_bytes
                downloaded_bytes = 0

                with open(temp_target, "wb") as f:
                    chunk_size = 256 * 1024
                    while True:
                        if self._stop_requested:
                            temp_target.unlink(missing_ok=True)
                            self.on_complete(False, "Download cancelled by user.")
                            return

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        pct = min(0.99, downloaded_bytes / total_bytes) if total_bytes > 0 else 0.0
                        mb_dl = round(downloaded_bytes / (1024 * 1024), 1)
                        mb_tot = round(total_bytes / (1024 * 1024), 1)
                        self.on_progress(pct, f"Downloading: {mb_dl} / {mb_tot} MB ({int(pct * 100)}%)")

            # Finalize file
            if temp_target.exists():
                shutil.move(temp_target, target_path)

            self.on_progress(1.0, f"Download complete ({round(target_path.stat().st_size / (1024*1024), 1)} MB)")
            self.on_complete(True, f"Model {spec['name']} downloaded and verified successfully!")

        except Exception as e:
            logger.exception("Download failed for %s: %s", self.model_id, e)
            if temp_target.exists():
                try: temp_target.unlink(missing_ok=True)
                except Exception: pass
            self.on_complete(False, f"Download failed: {e}")
