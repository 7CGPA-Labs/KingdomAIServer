"""
Build packaging script creating KingdomServer-win64-full.zip release archive.
"""
import os
import shutil
import zipfile
from pathlib import Path

def create_release_archive():
    project_root = Path(__file__).resolve().parent.parent
    dist_dir = project_root / "dist" / "kingdom"
    build_out_dir = project_root / "release"
    build_out_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = build_out_dir / "KingdomServer-win64-full.zip"
    print(f"Creating release package at: {zip_path}")

    # Prepare staging directory
    staging_dir = build_out_dir / "KingdomServer-win64-full"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    # 1. Copy source codebase package
    src_dir = staging_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    for item in ["kingdom_server", "pyproject.toml", "README.md", "LICENSE", "main.py", "start_server.py", "download_models.py"]:
        target = project_root / item
        if target.is_dir():
            shutil.copytree(target, src_dir / item)
        elif target.is_file():
            shutil.copy(target, src_dir / item)

    # 2. Copy Deploy-KingdomServer.ps1 script
    deploy_script = project_root / "Deploy-KingdomServer.ps1"
    if deploy_script.exists():
        shutil.copy(deploy_script, staging_dir / "Deploy-KingdomServer.ps1")

    # 3. Create models directory placeholder
    models_dir = staging_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "README.txt").write_text(
        "Place the 9 ONNX model files/directories here:\n"
        "- qwen2.5-coder-1.5b-onnx/\n"
        "- all-MiniLM-L6-v2.onnx\n"
        "- bge-small-en-v1.5.onnx\n"
        "- bge-reranker-base.onnx\n"
        "- codeberta-base.onnx\n"
        "- granite-code-128m.onnx\n"
        "- nli-deberta-v3-small.onnx\n"
        "- codebert-vulnerability.onnx\n"
        "- MobileDiffusion-LCM.onnx\n",
        encoding="utf-8"
    )

    # 4. Zip everything up into KingdomServer-win64-full.zip
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(staging_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(staging_dir)
                zipf.write(file_path, arcname)

    print(f"Release package created successfully! Size: {zip_path.stat().st_size / (1024*1024):.2f} MB")
    return zip_path

if __name__ == "__main__":
    create_release_archive()
