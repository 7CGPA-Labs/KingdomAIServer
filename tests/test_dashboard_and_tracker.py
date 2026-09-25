"""
Unit Tests for K-Top (Kingdom Top) Dashboard, Request Tracker, and Log Buffer.
Verifies:
- RequestTracker metrics recording and in-memory ring buffer
- RingBufferLogHandler interceptor
- KingdomTopDashboard layout components and meter rendering
- Middleware request integration
"""
import logging
from fastapi.testclient import TestClient

from src.utils.request_tracker import RequestTracker, tracker
from src.utils.log_buffer import RingBufferLogHandler, attach_log_interceptor
from src.cli.server_dashboard import KingdomTopDashboard, make_meter
from src.inference.inference_engine import app, LOCAL_BEARER_TOKEN

client = TestClient(app)

def test_request_tracker_operations():
    """Verify RequestTracker records request lifecycles and throughput metrics."""
    test_tracker = RequestTracker()
    test_tracker.clear()

    assert test_tracker.get_active_count() == 0
    assert len(test_tracker.get_recent_requests()) == 0

    # Start request
    test_tracker.record_request_start("req-test-1", "POST", "/v1/chat/completions", priority="NORMAL")
    assert test_tracker.get_active_count() == 1
    assert len(test_tracker.get_recent_requests()) == 1

    req = test_tracker.get_recent_requests()[0]
    assert req["id"] == "req-test-1"
    assert req["status"] == "RUNNING"

    # End request
    test_tracker.record_request_end("req-test-1", status_code=200, tokens_generated=50, tokens_per_sec=25.0)
    assert test_tracker.get_active_count() == 0

    req_ended = test_tracker.get_recent_requests()[0]
    assert req_ended["status"] == "200"
    assert req_ended["tokens"] == 50
    assert req_ended["tokens_per_sec"] == 25.0

    stats = test_tracker.get_stats()
    assert stats["total_requests"] == 1
    assert stats["total_tokens_generated"] == 50
    assert stats["last_tokens_per_sec"] == 25.0

def test_ring_buffer_log_handler():
    """Verify log records are intercepted into the sliding ring buffer."""
    handler = RingBufferLogHandler(capacity=10)
    handler.clear()

    logger = logging.getLogger("test.ktop")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Test server event 1")
    logger.warning("Test server event 2")

    logs = handler.get_recent_logs(limit=5)
    assert len(logs) == 2
    assert "Test server event 1" in logs[0]
    assert "Test server event 2" in logs[1]

    # Test interceptor attachment
    interceptor = attach_log_interceptor(level=logging.INFO)
    assert interceptor is not None

def test_make_meter():
    """Verify ASCII meter bar generation for percentages."""
    meter_low = make_meter(25.0, width=20)
    assert "25.0%" in meter_low.plain

    meter_mid = make_meter(75.0, width=20)
    assert "75.0%" in meter_mid.plain

    meter_high = make_meter(95.0, width=20)
    assert "95.0%" in meter_high.plain

def test_kingdom_top_dashboard_layout():
    """Verify KingdomTopDashboard layout components render without errors."""
    dashboard = KingdomTopDashboard(host="127.0.0.1", port=58420, bearer_token="test-token")
    
    header = dashboard.render_header()
    assert header is not None

    gauges = dashboard.render_resource_gauges()
    assert gauges is not None

    council = dashboard.render_council_panel()
    assert council is not None

    requests_table = dashboard.render_requests_table()
    assert requests_table is not None

    logs = dashboard.render_log_pane()
    assert logs is not None

    footer = dashboard.render_footer()
    assert footer is not None

    # Full layout assembly
    layout = dashboard.build_layout()
    assert layout is not None

    # Help modal toggle
    dashboard.show_help = True
    help_layout = dashboard.build_layout()
    assert help_layout is not None

def test_middleware_request_tracking_integration():
    """Verify HTTP requests through FastAPI gateway are automatically recorded by tracker."""
    tracker.clear()
    headers = {"Authorization": f"Bearer {LOCAL_BEARER_TOKEN}"}
    payload = {
        "model": "qwen2.5-coder-1.5b",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False
    }

    resp = client.post("/v1/chat/completions", json=payload, headers=headers)
    assert resp.status_code == 200

    recent = tracker.get_recent_requests(limit=5)
    assert len(recent) >= 1
    matched = [r for r in recent if r["path"] == "/v1/chat/completions"]
    assert len(matched) >= 1
    assert matched[0]["status"] == "200"
