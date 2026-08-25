# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path

block_cipher = None

spec_dir = SPECPATH if 'SPECPATH' in globals() else os.path.abspath(".")
project_root = os.path.abspath(os.path.join(spec_dir, ".."))

datas = [
    (os.path.join(project_root, "kingdom_server"), "kingdom_server"),
]

binaries = []

# Collect dynamic C++ DLLs if present
possible_dll_dirs = [
    os.path.join(sys.prefix, "Lib", "site-packages", "onnxruntime", "capi"),
    os.path.join(sys.prefix, "Lib", "site-packages", "llama_cpp"),
    os.path.join(sys.prefix, "DLLs"),
]

for d in possible_dll_dirs:
    if os.path.exists(d):
        for f in os.listdir(d):
            if f.endswith(".dll") or f.endswith(".pyd"):
                binaries.append((os.path.join(d, f), "."))

a = Analysis(
    [os.path.join(project_root, "main.py")],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "kingdom_server",
        "kingdom_server.cli.commands",
        "kingdom_server.core.hardware",
        "kingdom_server.core.ministers",
        "kingdom_server.core.memory_vault",
        "kingdom_server.core.crawler",
        "kingdom_server.core.orchestrator",
        "kingdom_server.server.app",
        "kingdom_server.server.sse",
        "kingdom_server.tray.tray_app",
        "kingdom_server.utils.telemetry",
        "kingdom_server.utils.verifier",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "pystray",
        "PIL",
        "onnxruntime",
        "sqlite3",
        "psutil",
        "httpx",
        "typer",
        "rich",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='kingdom',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False, # Strictly user space non-admin execution (asInvoker)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='kingdom',
)
