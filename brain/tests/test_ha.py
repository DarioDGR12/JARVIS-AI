from fastapi.testclient import TestClient

from jarvis_brain.auth.howdy import AuthGate
from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.ha.client import HAConfig, HomeAssistant
from jarvis_brain.product.app import ProductRuntime, attach_product_routes


class FakeHermes:
    async def ping(self):
        return {"ok": True}

    async def ensure_session(self):
        return "s"


def test_ha_write_needs_auth(tmp_path) -> None:
    gate = AuthGate(compare=None, user="dario")
    runtime = ProductRuntime(
        cfg=BrainConfig(),
        bus=EventBus(),
        hermes=FakeHermes(),  # type: ignore[arg-type]
        tts=None,
        session_id="s",
        auth=gate,
        ha=HomeAssistant(HAConfig(url="http://127.0.0.1:18123", token="x")),
    )
    client = TestClient(attach_product_routes(EventBus().app(), runtime))
    r = client.post(
        "/api/ha/call",
        json={"domain": "light", "service": "toggle", "entity_id": "light.x"},
    )
    assert r.status_code == 403
    assert r.json()["auth"]["error"] == "no_model"


def test_system_endpoint() -> None:
    runtime = ProductRuntime(
        cfg=BrainConfig(),
        bus=EventBus(),
        hermes=FakeHermes(),  # type: ignore[arg-type]
        tts=None,
        session_id="s",
        auth=AuthGate(compare=None),
    )
    client = TestClient(attach_product_routes(EventBus().app(), runtime))
    r = client.get("/api/system")
    assert r.status_code == 200
    assert "stats" in r.json()
    assert "doctor" in r.json()
    doc = client.get("/api/doctor")
    assert doc.status_code == 200
    assert "checks" in doc.json()
    auth = client.get("/api/auth")
    assert auth.json()["enrolled"] is False
