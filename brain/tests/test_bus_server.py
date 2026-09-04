from fastapi.testclient import TestClient

from jarvis_brain.bus.envelope import new_event
from jarvis_brain.bus.server import EventBus


def test_health_and_http_publish() -> None:
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe(lambda ev: seen.append(ev.type))
    client = TestClient(bus.app())
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    posted = client.post(
        "/api/bus",
        json=new_event("user.text", {"text": "hola"}, source="qa").to_dict(),
    )
    assert posted.status_code == 200
    body = posted.json()
    assert body["type"] == "user.text"
    assert body["payload"]["text"] == "hola"
    assert "user.text" in seen


def test_ws_roundtrip() -> None:
    bus = EventBus()
    client = TestClient(bus.app())
    with client.websocket_connect("/ws/bus") as ws:
        ws.send_json(new_event("brain.status", {"state": "idle"}, source="qa").to_dict())
        echoed = ws.receive_json()
        assert echoed["type"] == "brain.status"
        assert echoed["payload"]["state"] == "idle"
