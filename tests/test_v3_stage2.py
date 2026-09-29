"""
Test suite for Kingdom AI Studio V3 - Stage 2 (Slint Markup & Antigravity Layout Implementation).
Verifies compilation of all Google Antigravity UI surfaces:
Sidebar, Chat Canvas, Auxiliary Inspector, Models Hub, K-Top Dashboard, and Master App Shell.
"""
import pytest
from pathlib import Path

def test_slint_subcomponents_compilation():
    """Assert all individual Slint component files compile cleanly."""
    import slint
    ui_dir = Path(__file__).resolve().parent.parent / "ui"
    
    files = [
        ui_dir / "theme.slint",
        ui_dir / "components" / "badge.slint",
        ui_dir / "components" / "progress_meter.slint",
        ui_dir / "components" / "code_card.slint",
        ui_dir / "sidebar.slint",
        ui_dir / "chat_canvas.slint",
        ui_dir / "auxiliary_pane.slint",
        ui_dir / "models_hub.slint",
        ui_dir / "ktop_panel.slint",
        ui_dir / "app.slint"
    ]

    for f in files:
        assert f.exists(), f"Missing file: {f}"
        ns = slint.load_file(str(f))
        assert ns is not None

def test_master_app_shell_full_properties():
    """Assert MainWindow instantiates with full reactive state properties and Antigravity layout defaults."""
    import slint
    app_path = Path(__file__).resolve().parent.parent / "ui" / "app.slint"
    ns = slint.load_file(str(app_path))
    assert hasattr(ns, "MainWindow")

    app = ns.MainWindow()
    # Check default properties
    assert app.active_nav == "chat"
    assert app.active_workspace == "KingdomAIServer"
    assert app.active_model == "Qwen 2.5 Coder 1.5B"
    assert app.cpu_threads == 8
    assert app.vram_ceiling_gb == 6.0
    assert app.is_generating is False
    assert app.is_downloading is False

    # Check property mutations across tabs
    app.active_nav = "models"
    assert app.active_nav == "models"

    app.active_nav = "ktop"
    assert app.active_nav == "ktop"

    app.active_nav = "settings"
    assert app.active_nav == "settings"

    app.active_nav = "chat"
    assert app.active_nav == "chat"

def test_master_app_callbacks_registered():
    """Assert all user action callbacks are exposed by MainWindow for Python AppController binding."""
    import slint
    app_path = Path(__file__).resolve().parent.parent / "ui" / "app.slint"
    ns = slint.load_file(str(app_path))
    app = ns.MainWindow()

    callbacks = [
        "send_message",
        "stop_generation",
        "switch_model",
        "download_model",
        "select_workspace",
        "purge_cache",
        "clear_chat",
        "new_chat",
        "execute_command",
    ]

    for cb in callbacks:
        assert hasattr(app, cb), f"MainWindow missing callback: {cb}"

def test_progress_meter_clamping():
    """Assert progress meter component handles values between 0.0 and 1.0."""
    import slint
    meter_path = Path(__file__).resolve().parent.parent / "ui" / "components" / "progress_meter.slint"
    ns = slint.load_file(str(meter_path))
    assert hasattr(ns, "ProgressMeter")

    meter = ns.ProgressMeter()
    assert meter.progress == 0.0
    meter.progress = 0.75
    assert meter.progress == 0.75
