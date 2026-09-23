"""
Build packaging script creating KingdomServer-win64-full.zip release archive using zipapp (.pyz).
"""
import os
import shutil
import zipfile
import compileall
import zipapp
from pathlib import Path

def create_release_archive():
    project_root = Path(__file__).resolve().parent.parent
    build_out_dir = project_root / "release"
    build_out_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = build_out_dir / "KingdomServer-win64-full.zip"
    print(f"Creating release package at: {zip_path}")

    # Prepare staging directories
    staging_dir = build_out_dir / "KingdomServer-win64-full"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)
    
    bin_dir = staging_dir / "bin"
    bin_dir.mkdir(parents=True)

    # 1. Prepare ZipApp staging
    zipapp_stage = build_out_dir / "zipapp_stage"
    if zipapp_stage.exists():
        shutil.rmtree(zipapp_stage)
    zipapp_stage.mkdir(parents=True)

    for item in ["src", "config"]:
        target = project_root / item
        if target.exists():
            shutil.copytree(target, zipapp_stage / item)
    
    for item in ["main.py", "start_server.py", "download_models.py"]:
        target = project_root / item
        if target.exists():
            shutil.copy(target, zipapp_stage / item)

    # We must KEEP the .py files inside the .pyz bundle. 
    # Python bytecode (.pyc) has a strict "magic number" tied to the exact minor version of Python (e.g., 3.11 vs 3.12).
    # If we delete the .py files, the .pyz will ONLY run on the exact Python version used by GitHub Actions.
    # By leaving the .py files inside the .pyz, the bundle remains a single file but is universally compatible.
    for pycache in zipapp_stage.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache)

    # Write router __main__.py for the zipapp (MUST be uncompiled source to satisfy zipapp)
    main_py_content = """import sys
import os

if len(sys.argv) > 1:
    cmd = sys.argv[1].lower()
    if cmd == "server":
        from main import start_server
        start_server()
    elif cmd == "cli":
        from src.cli import terminal_ui
        terminal_ui.main()
    elif cmd == "download":
        from src.utils import downloader
        downloader.main()
    else:
        print(f"Unknown command: {cmd}")
else:
    from main import start_server
    start_server()
"""
    (zipapp_stage / "__main__.py").write_text(main_py_content, encoding="utf-8")

    # Create the zipapp
    pyz_path = bin_dir / "kingdom.pyz"
    print(f"Bundling into {pyz_path}...")
    zipapp.create_archive(source=zipapp_stage, target=pyz_path)
    shutil.rmtree(zipapp_stage)

    # 2. Copy Deploy script
    deploy_script = project_root / "Deploy-KingdomServer.ps1"
    if deploy_script.exists():
        shutil.copy(deploy_script, staging_dir / "Deploy-KingdomServer.ps1")

    # 3. Create model README
    models_dir = staging_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "README.txt").write_text(
        "Place the V2 model files here (or run download_models.cmd):\n"
        "- qwen2.5-coder-1.5b-instruct-q4_k_m.gguf\n"
        "- bge-small-en-v1.5-q4_k_m.gguf\n"
        "- bge-reranker-base-q4_k_m.gguf\n",
        encoding="utf-8"
    )

    # 4. Create local .cmd wrappers in bin/ for testing or manual execution
    (bin_dir / "start_server.cmd").write_text(
        "@echo off\nsetlocal\nset PYTHONUTF8=1\ncd /d \"%~dp0..\"\npython \"%~dp0kingdom.pyz\" server %*\n", encoding="utf-8"
    )
    (bin_dir / "kingdom_cli.cmd").write_text(
        "@echo off\nsetlocal\nset PYTHONUTF8=1\ncd /d \"%~dp0..\"\npython \"%~dp0kingdom.pyz\" cli %*\n", encoding="utf-8"
    )
    (bin_dir / "download_models.cmd").write_text(
        "@echo off\nsetlocal\nset PYTHONUTF8=1\ncd /d \"%~dp0..\"\npython \"%~dp0kingdom.pyz\" download %*\n", encoding="utf-8"
    )

    # 5. Zip the final structure
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
