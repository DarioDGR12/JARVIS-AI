from fastapi.testclient import TestClient

from jarvis_brain.bus.envelope import new_event
from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.hud.state import HUD_VIEWS, HudState
from jarvis_brain.product.app import ProductRuntime, attach_product_routes
from jarvis_brain.turn import collect_bus_events, run_text_turn


class FakeHermes:
    async def ping(self):
        return {"ok": True}

    async def ensure_session(self):
        return "s-hud"

    async def chat_stream(self, session_id, user_text, *, instructions):
        yield StreamEvent("assistant.delta", {"delta": "ok"})
        yield StreamEvent("run.completed", {"ok": True})


def _client() -> TestClient:
    bus = EventBus()
    runtime = ProductRuntime(
        cfg=BrainConfig(),
        bus=bus,
        hermes=FakeHermes(),  # type: ignore[arg-type]
        tts=None,
        session_id="s-hud",
    )
    return TestClient(attach_product_routes(bus.app(), runtime))


def test_hud_state_machine() -> None:
    hud = HudState()
    assert hud.operational == "boot"
    assert hud.view == "home"
    hud.apply(new_event("hud.set_mode", {"operational": "listening", "visual": "companion"}, source="brain"))
    assert hud.operational == "listening"
    assert hud.visual == "companion"
    hud.apply(new_event("hud.show_view", {"view": "chat"}, source="hud"))
    assert hud.view == "chat"
    assert hud.show_view("nope") is False
    hud.apply(new_event("hud.display", {"kind": "toast", "content": "hi", "title": "t"}, source="brain"))
    assert hud.last_display["content"] == "hi"
    assert hud.toasts[-1]["kind"] == "toast"
    hud.apply(new_event("hud.speak", {"text": "hello", "voice": "jarvis"}, source="voice"))
    assert hud.operational == "speaking"
    assert hud.last_speak["text"] == "hello"
    hud.apply(new_event("hud.highlight", {"target": "light.sala", "reason": "focus"}, source="brain"))
    assert hud.last_display["kind"] == "highlight"
    hud.apply(new_event("brain.status", {"state": "thinking"}, source="brain"))
    assert hud.operational == "thinking"
    hud.apply(new_event("persona.changed", {"to": "jarvis"}, source="brain"))
    assert hud.visual == "jarvis"
    hud.apply(new_event("auth.challenge", {"reason": "ha.command"}, source="brain"))
    assert hud.camera_hold is True
    assert hud.operational == "alert"
    hud.apply(new_event("auth.result", {"ok": True}, source="auth"))
    assert hud.camera_hold is False
    assert hud.operational == "standby"
    hud.apply(new_event("hud.ready", {"views": list(HUD_VIEWS)}, source="hud"))
    assert hud.ready is True
    snap = hud.snapshot()
    assert set(snap["views"]) == set(HUD_VIEWS)


def test_hud_api_view_click_ready() -> None:
    client = _client()
    status = client.get("/api/status").json()
    assert status["hud"]["view"] == "home"
    assert status["hud"]["operational"] == "boot"
    bad = client.post("/api/hud/view", json={"view": "spaceship"})
    assert bad.status_code == 400
    shown = client.post("/api/hud/view", json={"view": "system"})
    assert shown.status_code == 200
    assert shown.json()["view"] == "system"
    click = client.post("/api/hud/click", json={"target": "nav", "id": "system", "method": "pointer"})
    assert click.status_code == 200
    ready = client.post("/api/hud/ready", json={"camera": False, "viewport": {"w": 960, "h": 640}})
    assert ready.status_code == 200
    body = ready.json()
    assert body["ready"] is True
    assert "map" in body["views"]
    hud = client.get("/api/hud").json()
    assert hud["ok"] is True
    assert hud["view"] == "system"
    assert hud["ready"] is True


def test_chat_leaves_hud_standby() -> None:
    client = _client()
    chat = client.post("/api/chat", json={"message": "hola"})
    assert chat.status_code == 200
    hud = chat.json()["hud"]
    assert hud["operational"] == "standby"
    assert hud["last_display"] is None


async def test_phrase_map_paints_hud() -> None:
    bus = EventBus()
    seen = collect_bus_events(bus)
    hud = HudState()
    bus.subscribe(hud.apply)
    reply = await run_text_turn(
        user_text="cómo está el sistema",
        cfg=BrainConfig(),
        hermes=FakeHermes(),  # type: ignore[arg-type]
        bus=bus,
        session_id="s-hud",
    )
    assert reply.startswith("Sistema:")
    types = [e.type for e in seen]
    assert "hud.display" in types
    assert types[-1] == "hud.set_mode"
    assert hud.operational == "standby"
    assert hud.last_display is not None
    assert "Sistema" in (hud.last_display.get("content") or "")
