from fastapi.testclient import TestClient

from jarvis_brain.bus.envelope import new_event
from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.hud.state import HudState
from jarvis_brain.map.briefing import brief_world
from jarvis_brain.memory.store import LocalMemory
from jarvis_brain.product.app import ProductRuntime, attach_product_routes
from jarvis_brain.tools.phrase_map import match_phrase
from jarvis_brain.tools.watchdog import Watchdog
from jarvis_brain.turn import collect_bus_events, run_text_turn
from jarvis_brain.vision.capture import GrabResult
from jarvis_brain.vision.service import VisionService
from io import BytesIO

from PIL import Image


class FakeHermes:
    async def ping(self):
        return {"ok": True}

    async def chat_stream(self, session_id, user_text, *, instructions):
        yield StreamEvent("assistant.delta", {"delta": "Veo " + instructions[-24:]})
        yield StreamEvent("run.completed", {"ok": True})


def _png(color=(9, 9, 9)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, format="PNG")
    return buf.getvalue()


def _client(**kwargs) -> TestClient:
    bus = EventBus()
    runtime = ProductRuntime(
        cfg=BrainConfig(),
        bus=bus,
        hermes=FakeHermes(),  # type: ignore[arg-type]
        tts=None,
        session_id="s-r1",
        **kwargs,
    )
    return TestClient(attach_product_routes(bus.app(), runtime))


def test_phrases_round1() -> None:
    assert match_phrase("explica la pantalla").action == "vision.explain"
    assert match_phrase("explica la pantalla").handoff is True
    assert match_phrase("pon el visor").action == "hud.visor"
    assert match_phrase("pon el visor").payload["enabled"] is True
    assert match_phrase("quita el visor").payload["enabled"] is False
    assert match_phrase("recuerda que Dario usa Pop").action == "memory.add"
    assert match_phrase("olvida Pop").action == "memory.forget"
    assert match_phrase("briefing").action == "map.brief"
    assert match_phrase("qué pasa en Tokio").action == "map.brief"
    assert "Tokio" in match_phrase("qué pasa en Tokio").reply
    assert match_phrase("dónde está Tokio").action == "map.focus"
    assert match_phrase("cómo está la casa").action == "ha.status"


def test_watchdog_trips_once() -> None:
    dog = Watchdog(load_max=1.0, ram_max=50, temp_max=40, cooldown_s=999)
    first = dog.check({"load": [2.0, 1.0, 1.0], "mem_used_pct": 10, "cpu_temp_c": 30})
    second = dog.check({"load": [2.0, 1.0, 1.0], "mem_used_pct": 10, "cpu_temp_c": 30})
    assert first and first[0]["id"] == "load"
    assert second == []


def test_briefing_uses_catalog() -> None:
    feeds = [{"id": "madrid", "loc": "Madrid", "country": "ES", "lat": 40.4, "lon": -3.7, "region": "", "tags": []}]
    text = brief_world("madrid", feeds=feeds)
    assert "Madrid" in text


def test_voice_wake_and_surv_gate() -> None:
    client = _client()
    wake = client.post("/api/voice/wake", json={"phrase": "jarvis"})
    assert wake.status_code == 200
    assert wake.json()["operational"] == "listening"
    assert client.get("/api/voice").json()["wake"] == "stub"
    arm = client.post("/api/surveillance/arm", json={"armed": True})
    assert arm.status_code == 403
    alert = client.post("/api/surveillance/alert", json={"camera": "door", "text": "visita"})
    assert alert.status_code == 200
    assert client.get("/api/surveillance").json()["last"]["text"] == "visita"
    visor = client.post("/api/hud/visor", json={"enabled": True})
    assert visor.json()["visor"] is True
    seat = client.post("/api/hud/presence", json={"present": True})
    assert seat.json()["presence"] is True


def test_memory_phrase(tmp_path) -> None:
    mem = LocalMemory(tmp_path / "m.jsonl")
    client = _client(memory=mem)
    r = client.post("/api/chat", json={"message": "recuerda que el salón es light.sala"})
    assert r.status_code == 200
    assert "Anotado" in r.json()["reply"]
    hits = mem.search("salón")
    assert hits


async def test_explain_handoff_reaches_hermes() -> None:
    vis = VisionService(grab=lambda: GrabResult(png=_png((3, 4, 5)), backend="test", width=64, height=48))
    bus = EventBus()
    seen = collect_bus_events(bus)
    reply = await run_text_turn(
        user_text="explica la pantalla",
        cfg=BrainConfig(),
        hermes=FakeHermes(),  # type: ignore[arg-type]
        bus=bus,
        session_id="s-r1",
        vision=vis,
    )
    assert "Veo" in reply
    types = [e.type for e in seen]
    assert "vision.screen_context" in types
    assert "hud.highlight" in types
    assert types.count("assistant.text") >= 1


def test_hud_visor_presence_events() -> None:
    hud = HudState()
    hud.apply(new_event("hud.visor", {"enabled": True}, source="brain"))
    hud.apply(new_event("hud.presence", {"present": False}, source="hud"))
    assert hud.visor is True
    assert hud.presence is False
