from fastapi.testclient import TestClient

from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.product.app import ProductRuntime, attach_product_routes


class FakeHermes:
    async def ping(self):
        return {"ok": True}

    async def chat_stream(self, session_id, user_text, *, instructions):
        yield StreamEvent("assistant.delta", {"delta": f"Heard: {user_text}"})
        yield StreamEvent("run.completed", {"ok": True})


def test_console_and_chat() -> None:
    bus = EventBus()
    runtime = ProductRuntime(
        cfg=BrainConfig(),
        bus=bus,
        hermes=FakeHermes(),  # type: ignore[arg-type]
        tts=None,
        session_id="s-console",
    )
    client = TestClient(attach_product_routes(bus.app(), runtime))
    page = client.get("/")
    assert page.status_code == 200
    assert "JARVIS" in page.text
    status = client.get("/api/status")
    assert status.status_code == 200
    chat = client.post("/api/chat", json={"message": "hola"})
    assert chat.status_code == 200
    body = chat.json()
    assert body["ok"] is True
    assert "hola" in body["reply"]
