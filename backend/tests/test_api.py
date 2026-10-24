"""REST / WebSocket 接口测试（使用临时数据库，运行时后台任务关闭）。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _steps_payload():
    gestures = ("ONE", "TWO", "THREE", "FOUR", "FIVE")
    return [
        {
            "order": index + 1,
            "name": f"测试步骤 {index + 1}",
            "expected_gesture": gesture,
            "description": "",
            "timeout_seconds": 20,
            "enabled": True,
            "required": True,
        }
        for index, gesture in enumerate(gestures)
    ]


def test_health_and_ready(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["database"]["status"] == "UP"
    assert body["data"]["model"]["simulated"] is True

    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["data"]["checks"]["database"] == "UP"


def test_dashboard_summary(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["station"]["id"] == "TEST-01"
    assert data["stats"]["sessions_total"] == 0
    assert data["runtime"]["simulated"] is True


def test_sop_config_crud_and_validation(client: TestClient) -> None:
    steps = client.get("/api/v1/sop/steps").json()["data"]
    assert len(steps["items"]) == 5
    assert steps["items"][0]["expected_gesture"] == "ONE"

    payload = {"steps": _steps_payload()}
    saved = client.put("/api/v1/sop/steps", json=payload)
    assert saved.status_code == 200
    assert saved.json()["data"]["note"]

    invalid_order = {"steps": _steps_payload()}
    invalid_order["steps"][1]["order"] = 9
    bad = client.put("/api/v1/sop/steps", json=invalid_order)
    assert bad.status_code == 422
    assert bad.json()["code"] == 42200

    duplicate = {"steps": _steps_payload()}
    duplicate["steps"][1]["expected_gesture"] = "ONE"
    bad_duplicate = client.put("/api/v1/sop/steps", json=duplicate)
    assert bad_duplicate.status_code == 422

    reset = client.post("/api/v1/sop/steps/reset")
    assert reset.status_code == 200
    assert len(reset.json()["data"]["items"]) == 5


def test_simulation_skip_and_event_workflow(client: TestClient) -> None:
    start = client.post("/api/v1/monitor/session/start")
    assert start.status_code == 200
    assert start.json()["data"]["session"]["status"] == "RUNNING"

    injected = client.post("/api/v1/system/simulation", json={"action": "skip"})
    assert injected.status_code == 200

    current = client.get("/api/v1/monitor/current").json()["data"]
    assert current["session"]["status"] == "FAILED"
    assert current["session"]["compliance"] is False
    assert current["session"]["anomaly_count"] >= 2

    events = client.get("/api/v1/events", params={"page_size": 10, "include_info": True})
    assert events.status_code == 200
    items = events.json()["data"]["items"]
    types = {item["event_type"] for item in items}
    assert "SKIPPED_STEP" in types
    assert "ORDER_ERROR" in types

    anomaly = next(item for item in items if item["event_type"] == "ORDER_ERROR")
    acked = client.post(f"/api/v1/events/{anomaly['id']}/status", json={"status": "ACKED"})
    assert acked.status_code == 200
    assert acked.json()["data"]["status"] == "ACKED"

    resolved = client.post(f"/api/v1/events/{anomaly['id']}/status", json={"status": "RESOLVED"})
    assert resolved.status_code == 200
    assert resolved.json()["data"]["status"] == "RESOLVED"

    rollback = client.post(f"/api/v1/events/{anomaly['id']}/status", json={"status": "ACKED"})
    assert rollback.status_code == 409


def test_history_session_detail(client: TestClient) -> None:
    client.post("/api/v1/monitor/session/start")
    client.post("/api/v1/system/simulation", json={"action": "skip"})

    listing = client.get("/api/v1/history/sessions", params={"page": 1, "page_size": 10})
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert items
    session_id = items[0]["id"]

    detail = client.get(f"/api/v1/history/sessions/{session_id}")
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["session"]["id"] == session_id
    assert data["steps"]
    assert data["events"]


def test_session_control_conflicts(client: TestClient) -> None:
    stop = client.post("/api/v1/monitor/session/stop", json={"reason": "test"})
    assert stop.status_code == 409

    client.post("/api/v1/monitor/session/start")
    duplicate = client.post("/api/v1/monitor/session/start")
    assert duplicate.status_code == 409


def test_system_status_and_config(client: TestClient) -> None:
    status = client.get("/api/v1/system/status")
    assert status.status_code == 200
    data = status.json()["data"]
    # runtime_enabled=False 时不启动模型加载任务，因此状态保持 UNLOADED，
    # 但检测器本身仍标记为模拟来源，界面不会误报真实 AI。
    assert data["model"]["status"] == "UNLOADED"
    assert data["model"]["simulated"] is True
    assert data["camera"]["status"] == "OFF"
    assert data["database"]["status"] == "UP"

    config = client.get("/api/v1/system/config").json()["data"]
    assert config["inference_mode"] == "mock"
    assert config["camera_mode"] == "off"

    logs = client.get("/api/v1/system/logs")
    assert logs.status_code == 200


def test_backend_console_page(client: TestClient) -> None:
    response = client.get("/console")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "后端控制台" in response.text
    assert 'const API = "/api/v1"' in response.text
    assert "btnStart" in response.text

    root = client.get("/")
    assert root.status_code == 200
    assert "后端控制台" in root.text


def test_websocket_hello(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws/monitor") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "hello"
        assert "snapshot" in message["data"]
        assert "system" in message["data"]
