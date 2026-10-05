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
    ui_dir = Path(__file__).resolve().parent.parent / "src" / "gui" / "ui"
    
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
        ui_dir / "tasks_panel.slint",
        ui_dir / "skills_panel.slint",
        ui_dir / "projects_panel.slint",
        ui_dir / "settings_modal.slint",
        ui_dir / "app.slint"
    ]

    for f in files:
        assert f.exists(), f"Missing file: {f}"
        ns = slint.load_file(str(f))
        assert ns is not None

def test_master_app_shell_full_properties():
    """Assert MainWindow instantiates with full reactive state properties and Antigravity layout defaults."""
    import slint
    app_path = Path(__file__).resolve().parent.parent / "src" / "gui" / "ui" / "app.slint"
    ns = slint.load_file(str(app_path))
    assert hasattr(ns, "MainWindow")

    app = ns.MainWindow()
    # Check default properties
    assert app.active_nav == "chat"
    assert app.active_workspace == "KingdomAIServer"
    assert app.active_model == "Qwen 2.5 Coder 1.5B"
    assert app.active_mode == "normal"
    assert app.aux_active_tab == "council"
    assert app.cpu_threads == 8
    assert app.vram_ceiling_gb == 6.0
    assert app.is_generating is False
    assert app.is_downloading is False

    # Check property mutations across tabs
    app.active_nav = "models"
    assert app.active_nav == "models"

    app.active_nav = "ktop"
    assert app.active_nav == "ktop"

    app.active_nav = "tasks"
    assert app.active_nav == "tasks"

    app.active_nav = "skills"
    assert app.active_nav == "skills"

    app.active_nav = "projects"
    assert app.active_nav == "projects"

    app.active_nav = "settings"
    assert app.active_nav == "settings"

    app.active_nav = "chat"
    assert app.active_nav == "chat"

    # Check mode mutations
    app.active_mode = "plan"
    assert app.active_mode == "plan"
    app.active_mode = "goal"
    assert app.active_mode == "goal"

    # Check auxiliary inspector tab mutations
    app.aux_active_tab = "artifacts"
    assert app.aux_active_tab == "artifacts"
    app.aux_active_tab = "diffs"
    assert app.aux_active_tab == "diffs"

    # Antigravity 2.0 Collapse & Modal states
    assert app.is_sidebar_collapsed is False
    app.is_sidebar_collapsed = True
    assert app.is_sidebar_collapsed is True

    assert app.is_aux_collapsed is False
    app.is_aux_collapsed = True
    assert app.is_aux_collapsed is True

    assert app.show_settings_modal is False
    app.show_settings_modal = True
    assert app.show_settings_modal is True

    # Antigravity 2.0 Menu Dropdown States
    assert app.open_menu == ""
    app.open_menu = "file"
    assert app.open_menu == "file"
    app.open_menu = "antigravity"
    assert app.open_menu == "antigravity"
    app.open_menu = "view"
    assert app.open_menu == "view"
    app.open_menu = "window"
    assert app.open_menu == "window"
    app.open_menu = ""
    assert app.open_menu == ""

def test_master_app_callbacks_registered():
    """Assert all user action callbacks are exposed by MainWindow for Python AppController binding."""
    import slint
    app_path = Path(__file__).resolve().parent.parent / "src" / "gui" / "ui" / "app.slint"
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
        "set_mode",
        "mention_resource",
        "trigger_task",
        "cancel_task",
        "copy_text",
        "refresh_diff",
        "execute_plan",
        "add_task",
        "reload_skills",
        "close_requested",
        "minimize_requested",
        "maximize_requested",
        "drag_window",
    ]

    for cb in callbacks:
        assert hasattr(app, cb), f"MainWindow missing callback: {cb}"

def test_progress_meter_clamping():
    """Assert progress meter component handles values between 0.0 and 1.0."""
    import slint
    meter_path = Path(__file__).resolve().parent.parent / "src" / "gui" / "ui" / "components" / "progress_meter.slint"
    ns = slint.load_file(str(meter_path))
    assert hasattr(ns, "ProgressMeter")

    meter = ns.ProgressMeter()
    assert meter.progress == 0.0
    meter.progress = 0.75
    assert meter.progress == 0.75

def test_titlebar_controls_and_menus_integration():
    """Assert frameless title bar controls and menus integrate properly with AppController."""
    import slint
    from unittest.mock import MagicMock, patch
    from src.gui.app_controller import AppController

    mock_orch = MagicMock()
    mock_orch.model_name = "qwen2.5-coder-1.5b"
    mock_cache = MagicMock()
    mock_cache.stats.return_value = {"entries": 5, "hits": 2, "hit_ratio": 0.4}

    controller = AppController(orchestrator=mock_orch, cache_db=mock_cache)
    controller._register_callbacks()

    # Verify callback assignments
    assert controller.window.close_requested is not None
    assert controller.window.minimize_requested is not None
    assert controller.window.maximize_requested is not None
    assert controller.window.drag_window is not None

    # Test menu toggling via reactive property
    for menu in ["antigravity", "file", "view", "window"]:
        controller.window.open_menu = menu
        assert controller.window.open_menu == menu
    controller.window.open_menu = ""
    assert controller.window.open_menu == ""

    # Test minimize, maximize, and drag window handlers without exceptions
    with patch("ctypes.windll.user32.IsWindow", return_value=1), \
         patch("ctypes.windll.user32.ShowWindow") as mock_show, \
         patch("ctypes.windll.user32.IsZoomed", return_value=0), \
         patch("ctypes.windll.user32.GetAsyncKeyState", return_value=0x8000), \
         patch("ctypes.windll.user32.ReleaseCapture") as mock_rel, \
         patch("ctypes.windll.user32.SendMessageW") as mock_msg:
        
        controller._cached_hwnd = 12345
        
        controller.on_minimize_requested()
        mock_show.assert_called_with(12345, 6)

        controller.on_maximize_requested()
        mock_show.assert_called_with(12345, 3)

        controller.on_drag_window()
        mock_rel.assert_called_once()
        mock_msg.assert_called_with(12345, 0x0112, 0xF012, 0)


def test_end_to_end_wiring():
    """Assert end-to-end integration between frontend UI and in-process backend engines."""
    from src.gui.app_controller import AppController

    controller = AppController(auto_start_telemetry=False)
    assert controller.window is not None
    assert controller.window.active_model == "Qwen 2.5 Coder 1.5B"
    assert controller.window.active_workspace == "KingdomAIServer"

    # Command palette filter & execute
    assert len(controller.window.palette_commands) > 10
    controller.on_filter_palette_commands("toggle")
    assert len(controller.window.palette_commands) >= 2
    controller.on_filter_palette_commands("")

    initial_sidebar_state = controller.window.is_sidebar_collapsed
    controller.on_execute_palette_command("view-toggle-sidebar")
    assert controller.window.is_sidebar_collapsed != initial_sidebar_state
    controller.on_execute_palette_command("view-toggle-sidebar")
    assert controller.window.is_sidebar_collapsed == initial_sidebar_state

    # Project tree & conversations
    assert len(controller._projects_tree) >= 2
    p1 = controller._projects_tree[0]
    p1_convs = p1.get("conversations", [])
    assert len(p1_convs) > 0
    controller.on_select_conversation(p1["id"], p1_convs[0]["id"], p1["name"], p1_convs[0]["title"])
    assert controller.window.conversation_title == p1_convs[0]["title"]
    assert controller.window.active_workspace == p1["name"]

    # Auxiliary tabs
    controller.on_open_aux_tab("diff:test.py", "test.py", "diff", True, "diff")
    assert controller.window.aux_active_tab == "diff:test.py"
    controller.on_close_aux_tab("diff:test.py")
    assert controller.window.aux_active_tab != "diff:test.py"

    # Hardware telemetry
    controller.telemetry.update_once()
    assert controller.window.vram_status != ""

    # In-process streaming generation & event loop pumping
    initial_msg_count = len(controller._display_messages)
    test_prompt = "Write a python function to compute fibonacci"
    controller.on_send_message(test_prompt)

    finished = controller.pump_events_until(lambda: not controller.window.is_generating, timeout_sec=25.0)
    assert finished, "Inference did not complete in time"
    assert not controller.window.is_generating
    assert len(controller._display_messages) >= initial_msg_count + 2
    assert controller._display_messages[-1]["role"] == "assistant"

    # SQLite Response cache hit
    controller.on_send_message(test_prompt)
    finished_cache = controller.pump_events_until(lambda: not controller.window.is_generating, timeout_sec=3.0)
    assert finished_cache
    assert controller.cache_db.total_hits >= 1


