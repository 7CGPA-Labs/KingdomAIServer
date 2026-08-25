"""
Model auto-downloader module using httpx and Rich progress bars.
Fetches GGUF and ONNX model files from HuggingFace hub into %LocalAppData%\\KingdomAIServer\\models.
"""
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from rich.console import Console

from kingdom_server.utils import get_models_dir
from kingdom_server.utils.verifier import MODEL_MANIFEST, ModelVerifier

console = Console()

# HuggingFace Direct Download URLs for 9 Models
MODEL_DOWNLOAD_URLS: Dict[str, str] = {
    "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf": "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
    "all-MiniLM-L6-v2.onnx": "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/onnx/model.onnx",
    "bge-small-en-v1.5.onnx": "https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/main/onnx/model.onnx",
    "bge-reranker-base.onnx": "https://huggingface.co/BAAI/bge-reranker-base/resolve/main/onnx/model.onnx",
    "codeberta-base.onnx": "https://huggingface.co/huggingface/CodeBERTa-small-v1/resolve/main/onnx/model.onnx",
    "granite-code-128m.onnx": "https://huggingface.co/ibm-granite/granite-3.0-128m-instruct/resolve/main/onnx/model.onnx",
    "nli-deberta-v3-small.onnx": "https://huggingface.co/MoritzLaurer/DeBERTa-v3-small-mnli-fever-anli/resolve/main/onnx/model.onnx",
    "codebert-vulnerability.onnx": "https://huggingface.co/mrm8488/codebert-base-finetuned-detect-insecure-code/resolve/main/onnx/model.onnx",
    "MobileDiffusion-LCM.onnx": "https://huggingface.co/google/MobileDiffusion/resolve/main/onnx/model.onnx",
}

class ModelDownloader:
    """Manages downloading model binary files with Rich progress display."""

    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = Path(models_dir) if models_dir else get_models_dir()
        self.verifier = ModelVerifier(self.models_dir)

    def download_file(self, filename: str, url: str) -> bool:
        target_path = self.models_dir / filename
        spec = MODEL_MANIFEST.get(filename, {})
        model_name = spec.get("name", filename)

        console.print(f"[bold cyan]Downloading {model_name}...[/bold cyan]")
        console.print(f"URL: [dim]{url}[/dim]")

        try:
            with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as response:
                if response.status_code != 200:
                    console.print(f"[bold red]Failed to download {filename}: HTTP {response.status_code}[/bold red]")
                    return False

                total_bytes = int(response.headers.get("content-length", 0))

                with Progress(
                    TextColumn("[bold blue]{task.fields[filename]}"),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                    console=console
                ) as progress:
                    task_id = progress.add_task("download", filename=filename, total=total_bytes)

                    with open(target_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=1024 * 64):
                            f.write(chunk)
                            progress.update(task_id, advance=len(chunk))

            console.print(f"[bold green]✔ Successfully downloaded {filename}![/bold green]\n")
            return True
        except Exception as e:
            console.print(f"[bold red]Error downloading {filename}: {e}[/bold red]\n")
            if target_path.exists() and target_path.stat().st_size == 0:
                target_path.unlink(missing_ok=True)
            return False

    def download_missing(self) -> Dict[str, bool]:
        summary = self.verifier.get_summary()
        results = {}

        missing_models = [m for m in summary["details"] if m["status"] != "valid"]
        if not missing_models:
            console.print("[bold green]All 9 model files are already present and verified![/bold green]")
            return {}

        console.print(f"[bold yellow]Found {len(missing_models)} missing model files. Starting auto-download...[/bold yellow]\n")

        for m in missing_models:
            fn = m["filename"]
            url = MODEL_DOWNLOAD_URLS.get(fn)
            if url:
                results[fn] = self.download_file(fn, url)
            else:
                console.print(f"[yellow]No download URL specified for {fn}[/yellow]")
                results[fn] = False

        return results
