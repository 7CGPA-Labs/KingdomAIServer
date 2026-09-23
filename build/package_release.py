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
    codebase_dir = staging_dir / "src"
    codebase_dir.mkdir(parents=True, exist_ok=True)
    for item in ["src", "config", "pyproject.toml", "README.md", "LICENSE", "main.py", "start_server.py", "download_models.py"]:
        target = project_root / item
        dest = codebase_dir / item
        if target.is_dir():
            shutil.copytree(target, dest)
        elif target.is_file():
            shutil.copy(target, dest)

    # 2. Copy Deploy-KingdomServer.ps1 script
    deploy_script = project_root / "Deploy-KingdomServer.ps1"
    if deploy_script.exists():
        shutil.copy(deploy_script, staging_dir / "Deploy-KingdomServer.ps1")

    # 3. Compile everything to non-editable Python bytecode (.pyc)
    import compileall
    print("Compiling source code to non-editable bytecode (.pyc)...")
    # legacy=True puts the .pyc files right next to the .py files instead of inside __pycache__
    compileall.compile_dir(staging_dir, force=True, legacy=True, quiet=1)

    # Remove all original .py source files to secure the codebase
    for py_file in staging_dir.rglob("*.py"):
        py_file.unlink()
        
    # Clean up any residual __pycache__ directories
    for pycache in staging_dir.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache)

    # 4. Create models directory placeholder
    models_dir = staging_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "README.txt").write_text(
        "Place the V2 model files here (or run python download_models.py):\n"
        "- qwen2.5-coder-1.5b-instruct-q4_k_m.gguf\n"
        "- bge-small-en-v1.5-q4_k_m.gguf\n"
        "- bge-reranker-base-q4_k_m.gguf\n",
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
