"""
Model file verification module for SHA-256 integrity checks and pre-flight diagnostics.
"""
import hashlib
import os
from pathlib import Path
from typing import Dict, Any, List
from kingdom_server.utils import get_models_dir

# 9 Models Specification Manifest
MODEL_MANIFEST: Dict[str, Dict[str, Any]] = {
    "qwen2.5-coder-1.5b-onnx": {
        "id": "boss_qwen2.5",
        "name": "Senior Software Engineer (Main Boss)",
        "model_id": "Qwen2.5-Coder-1.5B-Instruct-ONNX",
        "approx_size_mb": 1100,
        "type": "onnx-genai",
        "sha256": None,
    },
    "all-MiniLM-L6-v2.onnx": {
        "id": "minister_1",
        "name": "Minister 1 (Intent Router)",
        "model_id": "all-MiniLM-L6-v2",
        "approx_size_mb": 25,
        "type": "onnx",
        "sha256": None,
    },
    "bge-small-en-v1.5.onnx": {
        "id": "minister_2",
        "name": "Minister 2 (Repo Embedder)",
        "model_id": "bge-small-en-v1.5",
        "approx_size_mb": 60,
        "type": "onnx",
        "sha256": None,
    },
    "bge-reranker-base.onnx": {
        "id": "minister_3",
        "name": "Minister 3 (Re-Ranker)",
        "model_id": "bge-reranker-base",
        "approx_size_mb": 110,
        "type": "onnx",
        "sha256": None,
    },
    "codeberta-base.onnx": {
        "id": "minister_4",
        "name": "Minister 4 (Code Parser)",
        "model_id": "codeberta-base",
        "approx_size_mb": 125,
        "type": "onnx",
        "sha256": None,
    },
    "granite-code-128m.onnx": {
        "id": "minister_5",
        "name": "Minister 5 (Speed Autocomplete)",
        "model_id": "granite-code-128m",
        "approx_size_mb": 130,
        "type": "onnx",
        "sha256": None,
    },
    "nli-deberta-v3-small.onnx": {
        "id": "minister_6",
        "name": "Minister 6 (Fact Checker)",
        "model_id": "nli-deberta-v3-small",
        "approx_size_mb": 90,
        "type": "onnx",
        "sha256": None,
    },
    "codebert-vulnerability.onnx": {
        "id": "minister_7",
        "name": "Minister 7 (Security Auditor)",
        "model_id": "codebert-vulnerability",
        "approx_size_mb": 125,
        "type": "onnx",
        "sha256": None,
    },
    "MobileDiffusion-LCM.onnx": {
        "id": "minister_8",
        "name": "Minister 8 (Asset & Diagram Generator)",
        "model_id": "MobileDiffusion-LCM",
        "approx_size_mb": 280,
        "type": "onnx",
        "sha256": None,
    },
}

class ModelVerifier:
    def __init__(self, models_dir: Path | None = None):
        self.models_dir = Path(models_dir) if models_dir else get_models_dir()

    def compute_sha256(self, filepath: Path, chunk_size: int = 1024 * 1024) -> str:
        """Compute SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    def verify_single_model(self, filename: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        target_file = self.models_dir / filename
        result = {
            "filename": filename,
            "name": spec["name"],
            "model_id": spec["model_id"],
            "expected_mb": spec["approx_size_mb"],
            "actual_mb": 0.0,
            "sha256": None,
            "status": "missing",
            "message": "File/Directory not found",
        }

        if not target_file.exists():
            return result

        if target_file.is_dir():
            # Auto-flatten double-nested extraction folder (e.g. qwen2.5-coder-1.5b-onnx/qwen2.5-coder-1.5b-onnx/)
            subdirs = [d for d in target_file.iterdir() if d.is_dir()]
            if len(subdirs) == 1 and not (target_file / "model.onnx").exists():
                nested_dir = subdirs[0]
                try:
                    import shutil
                    for item in nested_dir.iterdir():
                        dest = target_file / item.name
                        if not dest.exists():
                            shutil.move(item, dest)
                    shutil.rmtree(nested_dir, ignore_errors=True)
                except Exception:
                    pass

            total_bytes = sum(f.stat().st_size for f in target_file.glob("**/*") if f.is_file())
            size_mb = round(total_bytes / (1024 * 1024), 2)
            result["actual_mb"] = size_mb
            min_mb = spec["approx_size_mb"] * 0.4
            if size_mb >= min_mb:
                result["status"] = "valid"
                result["message"] = f"Directory present ({size_mb} MB)"
            else:
                result["status"] = "dummy"
                result["message"] = f"Incomplete directory ({size_mb} MB < min {round(min_mb, 1)} MB)"
            return result

        size_bytes = target_file.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        result["actual_mb"] = round(size_mb, 2)

        if size_bytes == 0:
            result["status"] = "corrupt"
            result["message"] = "Empty file (0 bytes)"
            return result

        expected_hash = spec.get("sha256")
        if expected_hash:
            actual_hash = self.compute_sha256(target_file)
            result["sha256"] = actual_hash
            if actual_hash.lower() == expected_hash.lower():
                result["status"] = "valid"
                result["message"] = "Integrity verified (SHA-256 match)"
            else:
                result["status"] = "corrupt"
                result["message"] = f"Hash mismatch (expected {expected_hash[:8]}...)"
            return result

        min_mb = spec["approx_size_mb"] * 0.4
        if size_mb < min_mb:
            result["status"] = "dummy"
            result["message"] = f"Placeholder/Dummy file ({result['actual_mb']} MB < min {round(min_mb, 1)} MB)"
            return result

        result["status"] = "valid"
        result["message"] = f"Present ({result['actual_mb']} MB)"
        return result

    def verify_all(self) -> List[Dict[str, Any]]:
        results = []
        for filename, spec in MODEL_MANIFEST.items():
            res = self.verify_single_model(filename, spec)
            results.append(res)
        return results

    def get_summary(self) -> Dict[str, Any]:
        results = self.verify_all()
        valid_count = sum(1 for r in results if r["status"] == "valid")
        total_count = len(MODEL_MANIFEST)
        return {
            "total": total_count,
            "valid": valid_count,
            "missing": total_count - valid_count,
            "all_healthy": valid_count == total_count,
            "details": results,
        }
