"""
Test suite for Kingdom AI Studio V3 - Stage 1 (Dependency & Environment Preparation).
Verifies Slint compiler, component instantiation, design tokens, and property bindings.
"""
import pytest
from pathlib import Path

def test_slint_package_import():
    """Assert slint package is installed and exposes compiler entrypoints."""
    import slint
    assert hasattr(slint, "load_file")
    assert hasattr(slint, "Component")
    assert hasattr(slint, "ListModel")

def _safe_load_slint(path):
    import slint
    try:
        return slint.load_file(str(path))
    except Exception as e:
        diags = getattr(e, "diagnostics", e.args[1] if hasattr(e, "args") and len(e.args) > 1 else [])
        details = "\n".join(str(d) for d in diags)
        raise AssertionError(f"Could not compile {path}:\n{details}") from e

def test_slint_theme_compilation():
    """Assert src/gui/ui/theme.slint compiles cleanly without syntax errors."""
    theme_path = Path(__file__).resolve().parent.parent / "src" / "gui" / "ui" / "theme.slint"
    assert theme_path.exists()
    ns = _safe_load_slint(theme_path)
    assert hasattr(ns, "ThemePreview")

def test_slint_badge_component():
    """Assert src/gui/ui/components/badge.slint compiles and instantiates StatusBadge."""
    badge_path = Path(__file__).resolve().parent.parent / "src" / "gui" / "ui" / "components" / "badge.slint"
    assert badge_path.exists()
    ns = _safe_load_slint(badge_path)
    assert hasattr(ns, "StatusBadge")
    badge = ns.StatusBadge()
    assert badge.text == "ACTIVE"

def test_slint_app_shell_compilation_and_bindings():
    """Assert src/gui/ui/app.slint compiles and provides two-way reactive property bindings."""
    app_path = Path(__file__).resolve().parent.parent / "src" / "gui" / "ui" / "app.slint"
    assert app_path.exists()
    ns = _safe_load_slint(app_path)
    assert hasattr(ns, "MainWindow")

    window = ns.MainWindow()
    assert window.active_model == "Qwen 2.5 Coder 1.5B"
    assert "GPU Accelerated" in window.silicon_provider
    assert window.is_generating is False

    # Test mutating properties dynamically
    window.active_model = "Qwen 2.5 Coder 3B"
    window.silicon_provider = "Vulkan GPU (Intel Iris Xe)"
    window.is_generating = True

    assert window.active_model == "Qwen 2.5 Coder 3B"
    assert window.silicon_provider == "Vulkan GPU (Intel Iris Xe)"
    assert window.is_generating is True

def test_gui_module_package_import():
    """Assert src.gui module package is discoverable."""
    import src.gui
    assert src.gui.__doc__ is not None
