"""
Thin-Client Model Auto-Provisioning module using urllib and curl.exe streaming.
Zero heavy dependencies. Downloads GGUF models strictly from GitHub Releases 
into %LocalAppData%\\KingdomAIServer\\models\\.
"""
import sys
import os
import ssl
import time
import shutil
import logging
import warnings
import subprocess
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

for proto in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    if proto in os.environ:
        os.environ[proto.upper()] = os.environ[proto]
        os.environ[proto.lower()] = os.environ[proto]

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    os.system("")

os.environ["CURL_CA_BUNDLE"] = ""
os.environ["PYTHONHTTPSVERIFY"] = "0"
warnings.filterwarnings("ignore")

from rich.progress import (
    Progress, TextColumn, BarColumn, DownloadColumn,
    TransferSpeedColumn, TimeRemainingColumn, TaskProgressColumn
)
from rich.console import Console

from src.utils import get_models_dir
from src.utils.verifier import MODEL_MANIFEST, ModelVerifier

logger = logging.getLogger("kingdom.downloader")
console = Console(safe_box=True)

# Strict GitHub Release Specification
MODEL_RELEASES = [
    "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
    "bge-small-en-v1.5-q4_k_m.gguf",
    "bge-reranker-base-q4_k_m.gguf"
]

class ModelDownloader:
    """Thin-client model auto-provisioning engine mapping strictly to GitHub Releases."""

    def __init__(self, models_dir: Optional[Path] = None):
        if models_dir is not None:
            self.models_dir = Path(models_dir)
        else:
            self.models_dir = get_models_dir()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.verifier = ModelVerifier(self.models_dir)

    def _finalize_model_file(self, temp_target: Path, target_filename: str):
        target_path = self.models_dir / target_filename
        if target_path.exists():
            if target_path.is_dir():
                shutil.rmtree(target_path, ignore_errors=True)
            else:
                target_path.unlink(missing_ok=True)
        shutil.move(temp_target, target_path)

    def is_html_block_page(self, filepath: Path) -> bool:
        """Checks if a downloaded file is an HTML proxy block page."""
        if not filepath.exists() or filepath.stat().st_size == 0:
            return True
        try:
            with open(filepath, "rb") as f:
                header = f.read(1024).lower()
                if b"<!doctype html" in header or b"<html" in header or b"zscaler" in header or b"403 forbidden" in header:
                    return True
        except Exception:
            pass
        return False

    def download_model(self, target_filename: str, progress: Optional[Progress] = None, task_id: Optional[Any] = None) -> bool:
        """Downloads a single model file exclusively from the GitHub Release tag."""
        if target_filename not in MODEL_RELEASES:
            return False

        manifest_spec = MODEL_MANIFEST.get(target_filename, {})
        target_path = self.models_dir / target_filename
        min_bytes = int(manifest_spec.get("approx_size_mb", 10) * 1024 * 1024 * 0.4)
        expected_bytes = manifest_spec.get("approx_size_mb", 10) * 1024 * 1024

        if target_path.exists() and (target_path.stat().st_size < min_bytes or self.is_html_block_page(target_path)):
            try: target_path.unlink(missing_ok=True)
            except Exception: pass

        if os.environ.get("SKIP_GITHUB_MIRROR"):
            # CI/CD Publishing fallback: Use HF CLI to fetch models to publish to GH Releases
            logger.info(f"CI/CD Mode: Downloading {target_filename} from HuggingFace Hub...")
            try:
                hf_cmd = ["huggingface-cli", "download", "--local-dir", str(self.models_dir)]
                if target_filename == "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf":
                    hf_cmd.extend(["Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF", target_filename])
                elif target_filename == "bge-small-en-v1.5-q4_k_m.gguf":
                    hf_cmd.extend(["CompendiumLabs/bge-small-en-v1.5-gguf", target_filename])
                elif target_filename == "bge-reranker-base-q4_k_m.gguf":
                    hf_cmd.extend(["sabafallah/bge-reranker-base-Q4_K_M-GGUF", target_filename])
                
                proc = subprocess.run(hf_cmd, check=True)
                return True
            except Exception as e:
                logger.error(f"HF CLI download failed: {e}")
                return False

        # Regular user download: from GH Releases
        download_url = f"https://github.com/7CGPA-Labs/KingdomAIServer/releases/download/v2.0.0-models/{target_filename}"
        temp_target = self.models_dir / f"{target_filename}.part"
        if temp_target.exists():
            try: temp_target.unlink(missing_ok=True)
            except Exception: pass

        headers = {"User-Agent": "Mozilla/5.0 KingdomAIServer/2.0", "Accept": "*/*"}
        errors = []

        # Strategy 1: urllib.request streaming
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(download_url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=600) as response:
                if response.status in (200, 302):
                    total_bytes = int(response.headers.get("Content-Length", 0))
                    if progress and task_id is not None and total_bytes > 0:
                        progress.update(task_id, total=total_bytes, completed=0)

                    first_chunk = True
                    with open(temp_target, "wb") as f:
                        while True:
                            chunk = response.read(1024 * 128)
                            if not chunk: break
                            if first_chunk:
                                first_chunk = False
                                if b"<!doctype html" in chunk[:512].lower():
                                    raise ValueError("HTML block page detected")
                            f.write(chunk)
                            if progress and task_id is not None:
                                progress.update(task_id, advance=len(chunk))

                    if temp_target.exists() and temp_target.stat().st_size >= min_bytes and not self.is_html_block_page(temp_target):
                        self._finalize_model_file(temp_target, target_filename)
                        if progress and task_id is not None:
                            size = target_path.stat().st_size
                            progress.update(task_id, total=size, completed=size)
                        return True
        except Exception as e:
            errors.append(f"urllib failed: {e}")
            if temp_target.exists(): temp_target.unlink(missing_ok=True)

        # Strategy 2: curl.exe fallback
        try:
            curl_cmd = ["curl.exe", "-L", "-k", "-s", "--retry", "5", "-C", "-", "-A", headers["User-Agent"], "-o", str(temp_target), download_url]
            proxy_env = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
            if proxy_env: curl_cmd.extend(["--proxy", proxy_env])
            
            proc = subprocess.Popen(curl_cmd)
            if progress and task_id is not None:
                progress.update(task_id, total=expected_bytes, completed=0)

            last_size = 0
            while proc.poll() is None:
                time.sleep(0.2)
                if temp_target.exists():
                    curr_size = temp_target.stat().st_size
                    delta = curr_size - last_size
                    if delta > 0 and progress and task_id is not None:
                        progress.update(task_id, advance=delta)
                        last_size = curr_size

            if proc.returncode == 0 and temp_target.exists() and temp_target.stat().st_size >= min_bytes and not self.is_html_block_page(temp_target):
                self._finalize_model_file(temp_target, target_filename)
                if progress and task_id is not None:
                    size = target_path.stat().st_size
                    progress.update(task_id, total=size, completed=size)
                return True
        except Exception as e:
            errors.append(f"curl failed: {e}")
            if temp_target.exists(): temp_target.unlink(missing_ok=True)

        logger.warning(f"Failed to download {target_filename} from GitHub: {errors}")
        return False

    def auto_provision_missing(self) -> Dict[str, bool]:
        for filename in MODEL_RELEASES:
            target_path = self.models_dir / filename
            manifest_spec = MODEL_MANIFEST.get(filename, {})
            min_bytes = int(manifest_spec.get("approx_size_mb", 10) * 1024 * 1024 * 0.4)
            if target_path.exists() and (target_path.stat().st_size < min_bytes or self.is_html_block_page(target_path)):
                try: target_path.unlink(missing_ok=True)
                except Exception: pass

        summary = self.verifier.get_summary()
        missing_models = [m for m in summary["details"] if m["status"] != "valid"]

        if not missing_models:
            console.print(f"[bold green]✔ All {summary['total']} GGUF model artifacts present.[/bold green]")
            return {}

        console.print(f"\n[bold gold1]📦 THIN-CLIENT MODEL AUTO-PROVISIONING (GitHub Releases)[/bold gold1]")
        console.print(f"[bold cyan]Downloading {len(missing_models)} missing models from GitHub into {self.models_dir}...[/bold cyan]\n")

        results = {}
        with Progress(TextColumn("[bold blue]{task.fields[name]}"), BarColumn(), TaskProgressColumn(), DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn(), console=console, refresh_per_second=10) as progress:
            tasks = {}
            for m in missing_models:
                fn = m["filename"]
                approx_bytes = int(MODEL_MANIFEST.get(fn, {}).get("approx_size_mb", 10) * 1024 * 1024)
                tasks[fn] = progress.add_task("download", name=m["name"], total=approx_bytes)

            for m in missing_models:
                fn = m["filename"]
                t_id = tasks[fn]
                success = self.download_model(fn, progress, t_id)
                results[fn] = success
                if not success:
                    progress.update(t_id, description=f"[red]Failed ({m['name']})[/red]")

        for p in self.models_dir.glob("*.part"):
            try: p.unlink(missing_ok=True)
            except Exception: pass

        post_summary = self.verifier.get_summary()
        console.print(f"\n[bold green]✔ Auto-provisioning complete! {post_summary['valid']}/{post_summary['total']} models verified.[/bold green]\n")
        return results

def main():
    downloader = ModelDownloader()
    downloader.auto_provision_missing()

if __name__ == "__main__":
    main()
