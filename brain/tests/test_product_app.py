from fastapi.testclient import TestClient

from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.product.app import ProductRuntime, attach_product_routes


class FakeHermes:
    async def ping(self):
        return {"ok": True}

    async def ensure_session(self):
        return "s-console"

    async def chat_stream(self, session_id, user_text, *, instructions):
        yield StreamEvent("assistant.delta", {"delta": f"Heard: {user_text}"})
        yield StreamEvent("run.completed", {"ok": True})


def _client() -> TestClient:
    bus = EventBus()
    runtime = ProductRuntime(
        cfg=BrainConfig(),
        bus=bus,
        hermes=FakeHermes(),  # type: ignore[arg-type]
        tts=None,
        session_id="s-console",
    )
    return TestClient(attach_product_routes(bus.app(), runtime))


def test_api_is_not_a_website() -> None:
    client = _client()
    page = client.get("/")
    assert page.status_code == 200
    body = page.json()
    assert body["ui"] == "desktop"
    assert "html" not in page.headers.get("content-type", "")


def test_chat_and_status() -> None:
    client = _client()
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["ui"] == "desktop"
    chat = client.post("/api/chat", json={"message": "hola"})
    assert chat.status_code == 200
    body = chat.json()
    assert body["ok"] is True
    assert "hola" in body["reply"]


def test_providers() -> None:
    client = _client()
    r = client.get("/api/providers")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()["providers"]}
    assert {"demo", "openai", "anthropic"} <= ids
