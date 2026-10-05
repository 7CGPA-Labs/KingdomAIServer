"""
Verification test for Kingdom AI Studio V3 release package (.zip and .pyz bundle).
"""
import zipfile
from pathlib import Path
import pytest

def test_v3_release_package_contents():
    """Verify release ZIP contains Slint UI assets, studio launcher, and kingdom.pyz bundle."""
    project_root = Path(__file__).resolve().parent.parent
    zip_path = project_root / "release" / "KingdomServer-win64-full.zip"
    
    if not zip_path.exists():
        from build.package_release import create_release_archive
        create_release_archive()

    assert zip_path.exists(), "Release package ZIP must exist after running package_release.py"

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()

        # Check required components in release structure
        assert any("bin/kingdom.pyz" in name for name in namelist)
        assert any("bin/kingdom_studio.cmd" in name for name in namelist)
        assert any("src/gui/ui/app.slint" in name or "ui/app.slint" in name for name in namelist)
        assert any("src/gui/ui/theme.slint" in name or "ui/theme.slint" in name for name in namelist)
        assert any("Deploy-KingdomServer.ps1" in name for name in namelist)

        # Inspect kingdom_studio.cmd content
        studio_cmd_entry = [n for n in namelist if n.endswith("kingdom_studio.cmd")][0]
        cmd_content = zf.read(studio_cmd_entry).decode("utf-8")
        assert "studio" in cmd_content
        assert "kingdom.pyz" in cmd_content

def test_v3_zipapp_bundle_contents(tmp_path):
    """Verify kingdom.pyz contains source files and V3 studio entrypoint."""
    project_root = Path(__file__).resolve().parent.parent
    pyz_path = project_root / "release" / "KingdomServer-win64-full" / "bin" / "kingdom.pyz"

    if not pyz_path.exists():
        from build.package_release import create_release_archive
        create_release_archive()

    with zipfile.ZipFile(pyz_path, "r") as zf:
        namelist = zf.namelist()

        assert "__main__.py" in namelist
        assert any("src/gui/app_controller.py" in name for name in namelist)
        assert any("src/core/local_llm.py" in name for name in namelist)
        assert any("src/gui/ui/app.slint" in name for name in namelist)

        # Verify default entrypoint boots studio
        main_code = zf.read("__main__.py").decode("utf-8")
        assert "launch_studio" in main_code
