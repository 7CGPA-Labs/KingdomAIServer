"""
Kingdom AI Studio V3 - Slint Toolchain & Environment Verification Script.
Validates Slint runtime, compiles ui/app.slint, and verifies property access.
"""
import sys
import os
from pathlib import Path

def verify_slint_environment():
    print("=" * 60)
    print(" [KINGDOM AI STUDIO V3] SLINT ENVIRONMENT VERIFICATION")
    print("=" * 60)

    # 1. Verify Slint Module
    try:
        import slint
        import importlib.metadata
        slint_version = importlib.metadata.version("slint")
        print(f"[OK] Slint package imported successfully. Version: {slint_version}")
    except ImportError as e:
        print(f"[ERROR] Failed to import slint: {e}")
        return False

    # 2. Check UI Directory Scaffolding
    project_root = Path(__file__).resolve().parent.parent
    ui_dir = project_root / "src" / "gui" / "ui"
    app_slint = ui_dir / "app.slint"
    theme_slint = ui_dir / "theme.slint"
    badge_slint = ui_dir / "components" / "badge.slint"

    for file_path, name in [(theme_slint, "src/gui/ui/theme.slint"), (badge_slint, "src/gui/ui/components/badge.slint"), (app_slint, "src/gui/ui/app.slint")]:
        if file_path.exists():
            print(f"[OK] Scaffolding file found: {name}")
        else:
            print(f"[ERROR] Missing scaffolding file: {name}")
            return False

    # 3. Dynamic Compilation of .slint Markup
    print("\nCompiling src/gui/ui/app.slint with native Slint compiler...")
    try:
        ns = slint.load_file(str(app_slint))
        if not hasattr(ns, "MainWindow"):
            print("[ERROR] 'MainWindow' component not found in compiled namespace.")
            return False
        print("[OK] src/gui/ui/app.slint compiled successfully.")
    except Exception as e:
        print(f"[ERROR] Compilation error: {e}")
        return False

    # 4. Component Instantiation & Property Model Verification
    try:
        window = ns.MainWindow()
        print(f"[OK] MainWindow component instantiated.")
        print(f"     Default active_model:      {window.active_model}")
        print(f"     Default silicon_provider:  {window.silicon_provider}")
        print(f"     Default vram_status:       {window.vram_status}")

        # Test mutating property
        window.active_model = "Qwen 2.5 Coder 3B (Upgraded)"
        window.silicon_provider = "Vulkan / GPU Accelerated (Intel Iris Xe)"
        window.vram_status = "2.90 / 6.00 GB"

        assert window.active_model == "Qwen 2.5 Coder 3B (Upgraded)"
        assert window.silicon_provider == "Vulkan / GPU Accelerated (Intel Iris Xe)"
        print("[OK] Two-way reactive property binding verified.")
    except Exception as e:
        print(f"[ERROR] Property binding error: {e}")
        return False

    # 5. Slint Backend Resolution
    active_backend = os.environ.get("SLINT_BACKEND", "default (DirectX/Vulkan/Auto)")
    print(f"\n[OK] Slint Graphics Backend: {active_backend}")
    print("=" * 60)
    print(" STAGE 1 SLINT ENVIRONMENT VERIFICATION: ALL CHECKS PASSED!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = verify_slint_environment()
    sys.exit(0 if success else 1)
