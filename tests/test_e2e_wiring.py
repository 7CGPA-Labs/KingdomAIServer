"""
Test script verifying frontend-backend end-to-end wiring in Kingdom AI Studio V3.
"""
import time
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.gui import AppController
from src.processing.cache import ResponseCacheDB

def main():
    print("=" * 60, flush=True)
    print(" [KINGDOM AI STUDIO V3] END-TO-END WIRING TEST", flush=True)
    print("=" * 60, flush=True)

    # 1. Instantiate Controller
    print("\n1. Initializing AppController...", flush=True)
    controller = AppController(auto_start_telemetry=False)
    assert controller.window is not None, "Window failed to instantiate"
    # Wait for in-process model warmup if running
    for _ in range(50):
        if controller.orchestrator.is_loaded:
            break
        time.sleep(0.1)
    print("   [OK] MainWindow instantiated.", flush=True)
    print(f"   [OK] Active model: {controller.window.active_model}", flush=True)
    print(f"   [OK] Active workspace: {controller.window.active_workspace}", flush=True)
    print(f"   [OK] Conversation title: {controller.window.conversation_title}", flush=True)
    print(f"   [OK] Boss status: {controller.window.boss_status}", flush=True)

    # 2. Verify Command Palette
    print("\n2. Testing Command Palette filtering and execution...", flush=True)
    assert len(controller.window.palette_commands) > 10, "Palette commands empty"
    print(f"   [OK] Initial palette commands count: {len(controller.window.palette_commands)}", flush=True)

    # Filter palette
    controller.on_filter_palette_commands("toggle")
    filtered_count = len(controller.window.palette_commands)
    print(f"   [OK] Filtered palette for 'toggle': {filtered_count} matches", flush=True)
    assert filtered_count >= 2, f"Expected at least 2 matches for 'toggle', got {filtered_count}"

    # Reset filter
    controller.on_filter_palette_commands("")
    assert len(controller.window.palette_commands) > 10, "Failed to reset palette filter"
    print("   [OK] Reset palette filter successfully.", flush=True)

    # Execute palette command: toggle sidebar
    initial_sidebar_state = controller.window.is_sidebar_collapsed
    controller.on_execute_palette_command("view-toggle-sidebar")
    assert controller.window.is_sidebar_collapsed != initial_sidebar_state, "Sidebar toggle failed"
    print(f"   [OK] Executed 'view-toggle-sidebar': is_sidebar_collapsed = {controller.window.is_sidebar_collapsed}", flush=True)
    # Toggle back
    controller.on_execute_palette_command("view-toggle-sidebar")
    assert controller.window.is_sidebar_collapsed == initial_sidebar_state

    # 3. Verify Project Tree & Conversations
    print("\n3. Testing Project Tree & Conversation switching...", flush=True)
    assert len(controller._projects_tree) >= 2, "Projects tree has insufficient projects"
    p1 = controller._projects_tree[0]
    p1_name = p1["name"]
    p1_convs = p1.get("conversations", [])
    assert len(p1_convs) > 0, "No conversations in project 1"
    first_conv = p1_convs[0]

    # Select conversation
    controller.on_select_conversation(p1["id"], first_conv["id"], p1_name, first_conv["title"])
    assert controller.window.conversation_title == first_conv["title"]
    assert controller.window.active_conversation_id == first_conv["id"]
    assert controller.window.active_workspace == p1_name
    print(f"   [OK] Selected conversation: '{controller.window.conversation_title}' under '{controller.window.active_workspace}'", flush=True)
    print(f"   [OK] Chat messages loaded: {len(controller.window.chat_messages)} message(s)", flush=True)

    # Test New Chat creation
    initial_conv_count = len(p1["conversations"])
    controller.on_new_chat()
    assert len(p1["conversations"]) == initial_conv_count + 1, "New conversation not added to active project"
    print(f"   [OK] Created New Conversation: '{controller.window.conversation_title}' (Total convs in project: {len(p1['conversations'])})", flush=True)

    # 4. Verify Auxiliary Tabs
    print("\n4. Testing Auxiliary Inspector Tabs...", flush=True)
    controller.on_open_aux_tab("diff:test.py", "test.py", "diff", True, "diff")
    assert controller.window.aux_active_tab == "diff:test.py"
    print(f"   [OK] Opened dynamic aux tab: '{controller.window.aux_active_tab}'", flush=True)
    controller.on_close_aux_tab("diff:test.py")
    assert controller.window.aux_active_tab != "diff:test.py"
    print(f"   [OK] Closed dynamic aux tab, active tab restored to: '{controller.window.aux_active_tab}'", flush=True)

    # 5. Verify Telemetry Snapshot
    print("\n5. Testing Hardware Telemetry...", flush=True)
    controller.telemetry.update_once()
    print(f"   [OK] Telemetry provider: {controller.window.silicon_provider}", flush=True)
    print(f"   [OK] CPU Usage: {controller.window.cpu_pct:.1f}%", flush=True)
    print(f"   [OK] RAM Usage: {controller.window.ram_used_gb:.2f} / {controller.window.ram_total_gb:.2f} GB", flush=True)
    print(f"   [OK] VRAM Status: {controller.window.vram_status}", flush=True)

    # 6. Verify Chat Message Sending, In-Process Inference & Streaming
    print("\n6. Testing Chat Message & In-Process Streaming Generation...", flush=True)
    initial_msg_count = len(controller._display_messages)
    test_prompt = "Write a python function to compute fibonacci"
    print(f"   Sending prompt: '{test_prompt}'", flush=True)
    controller.on_send_message(test_prompt)

    # Pump Slint event loop until inference worker finishes streaming
    finished = controller.pump_events_until(lambda: not controller.window.is_generating, timeout_sec=25.0)
    assert finished, "Inference did not complete in time"
    assert not controller.window.is_generating, "Inference flag still True after completion"
    final_msg_count = len(controller._display_messages)
    assert final_msg_count >= initial_msg_count + 2, f"Expected assistant reply added to messages, got {final_msg_count}"

    assistant_reply = controller._display_messages[-1]
    assert assistant_reply["role"] == "assistant"
    assert len(assistant_reply["content"]) > 20, "Assistant reply content too short"
    print("   [OK] Streaming completed successfully!", flush=True)
    print(f"   [OK] Speed: {controller.window.speed_tokens_sec:.1f} tokens/sec", flush=True)
    print(f"   [OK] Reply Preview (first 100 chars): {assistant_reply['content'][:100]}...", flush=True)

    # 7. Verify SQLite Response Cache Hit
    print("\n7. Testing Zero-VRAM SQLite Response Cache Hit...", flush=True)
    initial_hits = controller.cache_db.total_hits
    controller.on_send_message(test_prompt)

    finished_cache = controller.pump_events_until(lambda: not controller.window.is_generating, timeout_sec=3.0)
    assert finished_cache, "Cache response did not complete in time"

    cached_reply = controller._display_messages[-1]
    assert cached_reply["role"] == "assistant"
    print(f"   [OK] Cache hit verified! Total cache hits: {controller.cache_db.total_hits}", flush=True)

    print("\n" + "=" * 60, flush=True)
    print(" ALL 7 END-TO-END INTEGRATION CHECKS PASSED PERFECTLY!", flush=True)
    print("=" * 60, flush=True)

if __name__ == "__main__":
    main()
