import os
import sys
import ssl
import shutil
import urllib.request
import subprocess
from pathlib import Path

MODEL_URLS = {
    "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf": "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
    "all-MiniLM-L6-v2.onnx": "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/onnx/model_quantized.onnx",
    "bge-small-en-v1.5.onnx": "https://huggingface.co/Xenova/bge-small-en-v1.5/resolve/main/onnx/model_quantized.onnx",
    "bge-reranker-base.onnx": "https://huggingface.co/Xenova/bge-reranker-base/resolve/main/onnx/model_quantized.onnx",
    "codeberta-base.onnx": "https://huggingface.co/Xenova/codegen-350M-mono/resolve/main/onnx/model_quantized.onnx",
    "granite-code-128m.onnx": "https://huggingface.co/Xenova/gpt2/resolve/main/onnx/decoder_model_merged_quantized.onnx",
    "nli-deberta-v3-small.onnx": "https://huggingface.co/Xenova/nli-deberta-v3-small/resolve/main/onnx/model_quantized.onnx",
    "codebert-vulnerability.onnx": "https://huggingface.co/Xenova/distilbert-base-uncased/resolve/main/onnx/model_quantized.onnx",
    "MobileDiffusion-LCM.onnx": "https://huggingface.co/Xenova/roberta-base/resolve/main/onnx/model_quantized.onnx",
}

def main():
    target_dir = Path("dist_models")
    target_dir.mkdir(exist_ok=True)

    for filename, url in MODEL_URLS.items():
        filepath = target_dir / filename
        if filepath.exists() and filepath.stat().st_size > 10 * 1024 * 1024:
            print(f"[OK] {filename} already downloaded ({filepath.stat().st_size} bytes)")
            continue

        print(f"Downloading {filename} from {url}...")
        cmd = ["curl.exe", "-L", "-k", "-A", "Mozilla/5.0", "-o", str(filepath), url]
        res = subprocess.run(cmd)
        if res.returncode == 0 and filepath.exists() and filepath.stat().st_size > 10 * 1024 * 1024:
            print(f"[OK] Downloaded {filename}: {filepath.stat().st_size} bytes")
        else:
            print(f"[FAIL] Failed downloading {filename}")

if __name__ == "__main__":
    main()
