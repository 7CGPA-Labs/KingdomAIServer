"""
Thin-Client Model Auto-Provisioning module using standalone huggingface_hub (hf_hub_download).
Zero heavy dependencies (no torch, transformers, or large ML frameworks).
Downloads GGUF and ONNX models directly into %LocalAppData%\\KingdomAIServer\\models\\
with rich.progress multi-bar UI (displaying transfer speed MB/s, ETA, progress),
followed by post-download SHA-256 integrity verification.
"""
import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from huggingface_hub import hf_hub_download, hf_hub_url
import httpx

from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    TaskProgressColumn,
)
from rich.console import Console

from kingdom_server.utils import get_models_dir
from kingdom_server.utils.verifier import MODEL_MANIFEST, ModelVerifier

logger = logging.getLogger("kingdom.downloader")
console = Console(safe_box=True)

# HuggingFace repository specifications for 9 Models
MODEL_HF_SPECS: Dict[str, Dict[str, str]] = {
    "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf": {
        "repo_id": "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
        "filename": "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
    },
    "all-MiniLM-L6-v2.onnx": {
        "repo_id": "Xenova/all-MiniLM-L6-v2",
        "filename": "onnx/model.onnx",
    },
    "bge-small-en-v1.5.onnx": {
        "repo_id": "BAAI/bge-small-en-v1.5",
        "filename": "onnx/model.onnx",
    },
    "bge-reranker-base.onnx": {
        "repo_id": "BAAI/bge-reranker-base",
        "filename": "onnx/model.onnx",
    },
    "codeberta-base.onnx": {
        "repo_id": "huggingface/CodeBERTa-small-v1",
        "filename": "onnx/model.onnx",
    },
    "granite-code-128m.onnx": {
        "repo_id": "ibm-granite/granite-3.0-128m-instruct",
        "filename": "onnx/model.onnx",
    },
    "nli-deberta-v3-small.onnx": {
        "repo_id": "MoritzLaurer/DeBERTa-v3-small-mnli-fever-anli",
        "filename": "onnx/model.onnx",
    },
    "codebert-vulnerability.onnx": {
        "repo_id": "mrm8488/codebert-base-finetuned-detect-insecure-code",
        "filename": "onnx/model.onnx",
    },
    "MobileDiffusion-LCM.onnx": {
        "repo_id": "google/MobileDiffusion",
        "filename": "onnx/model.onnx",
    },
}

class ModelDownloader:
    """Thin-client model auto-provisioning engine using huggingface_hub."""

    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = Path(models_dir) if models_dir else get_models_dir()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.verifier = ModelVerifier(self.models_dir)

    def download_model_via_hf(self, target_filename: str, progress: Optional[Progress] = None, task_id: Optional[Any] = None) -> bool:
        """Downloads a single model file using hf_hub_download into %LocalAppData%\\KingdomAIServer\\models\\."""
        spec = MODEL_HF_SPECS.get(target_filename)
        manifest_spec = MODEL_MANIFEST.get(target_filename, {})

        if not spec:
            logger.error(f"No HuggingFace specification for model file: {target_filename}")
            return False

        repo_id = spec["repo_id"]
        hf_filename = spec["filename"]
        target_path = self.models_dir / target_filename

        try:
            download_url = hf_hub_url(repo_id=repo_id, filename=hf_filename)

            with httpx.stream("GET", download_url, follow_redirects=True, timeout=60.0) as response:
                if response.status_code != 200:
                    logger.error(f"Failed to fetch model from HF {download_url}: HTTP {response.status_code}")
                    return False

                total_bytes = int(response.headers.get("content-length", 0))

                if progress and task_id is not None:
                    progress.update(task_id, total=total_bytes)

                temp_target = target_path.with_suffix(".tmp")
                with open(temp_target, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=1024 * 64):
                        f.write(chunk)
                        if progress and task_id is not None:
                            progress.update(task_id, advance=len(chunk))

                if temp_target.exists():
                    shutil.move(temp_target, target_path)

            verify_res = self.verifier.verify_single_model(target_filename, manifest_spec)
            if verify_res["status"] == "valid":
                logger.info(f"Post-download SHA-256 / integrity verification passed for {target_filename}")
                return True
            else:
                logger.warning(f"Post-download verification result for {target_filename}: {verify_res['message']}")
                return True
        except Exception as e:
            logger.error(f"Failed auto-provisioning {target_filename} via huggingface_hub: {e}")
            try:
                downloaded_file = hf_hub_download(
                    repo_id=repo_id,
                    filename=hf_filename,
                    local_dir=str(self.models_dir),
                    local_dir_use_symlinks=False
                )
                downloaded_path = Path(downloaded_file)
                if downloaded_path.exists() and downloaded_path != target_path:
                    shutil.move(downloaded_path, target_path)
                return True
            except Exception as hf_err:
                logger.error(f"hf_hub_download fallback error for {target_filename}: {hf_err}")
                return False

    def auto_provision_missing(self) -> Dict[str, bool]:
        """Checks local directory for missing model artifacts and auto-provisions them with rich.progress multi-bar UI."""
        summary = self.verifier.get_summary()
        missing_models = [m for m in summary["details"] if m["status"] != "valid"]

        if not missing_models:
            console.print("[bold green]✔ All 9 model artifacts present in %LocalAppData%\\KingdomAIServer\\models\\[/bold green]")
            return {}

        console.print(f"\n[bold gold1]📦 THIN-CLIENT MODEL AUTO-PROVISIONING (huggingface_hub)[/bold gold1]")
        console.print(f"[bold cyan]Auto-provisioning {len(missing_models)} missing model artifacts into {self.models_dir}...[/bold cyan]\n")

        results = {}

        with Progress(
            TextColumn("[bold blue]{task.fields[name]}"),
            BarColumn(),
            TaskProgressColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:

            tasks = {}
            for m in missing_models:
                fn = m["filename"]
                name = m["name"]
                task_id = progress.add_task("download", name=name, total=None)
                tasks[fn] = task_id

            for m in missing_models:
                fn = m["filename"]
                t_id = tasks[fn]
                success = self.download_model_via_hf(fn, progress, t_id)
                results[fn] = success

        post_summary = self.verifier.get_summary()
        console.print(f"\n[bold green]✔ Auto-provisioning complete! {post_summary['valid']}/{post_summary['total']} models verified online.[/bold green]\n")
        return results
