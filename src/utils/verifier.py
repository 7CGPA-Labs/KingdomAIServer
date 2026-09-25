"""
Model file verification module for SHA-256 integrity checks and pre-flight diagnostics (V2 Engine).
"""
import hashlib
from pathlib import Path
from typing import Dict, Any, List
from src.utils import get_models_dir

# V2 Architecture Model Manifest (Main Boss GGUF + Lean 2-Minister Council)
MODEL_MANIFEST: Dict[str, Dict[str, Any]] = {
    "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf": {
        "id": "main_boss_qwen2.5",
        "name": "Senior Software Engineer (Main Boss GGUF)",
        "model_id": "Qwen2.5-Coder-1.5B-Instruct-GGUF",
        "approx_size_mb": 1100,
        "type": "gguf",
        "sha256": None,
    },
    "bge-small-en-v1.5-q4_k_m.gguf": {
        "id": "minister_1",
        "name": "Minister 1: Workspace Embedder (BGE-Small)",
        "model_id": "bge-small-en-v1.5",
        "approx_size_mb": 24,
        "type": "gguf",
        "sha256": None,
    },
    "bge-reranker-base-q4_k_m.gguf": {
        "id": "minister_2",
        "name": "Minister 2: Context Re-Ranker (BGE-ReRanker)",
        "model_id": "bge-reranker-base",
        "approx_size_mb": 208,
        "type": "gguf",
        "sha256": None,
    }
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
