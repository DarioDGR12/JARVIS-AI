from datetime import datetime
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from jarvis_brain.auth.howdy import AuthGate
from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.ha.schematic import build_schematic
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.memory.layered import LayeredMemory
from jarvis_brain.memory.lexical import lexical_score, rank_texts
from jarvis_brain.memory.store import LocalMemory
from jarvis_brain.product.app import ProductRuntime, attach_product_routes
from jarvis_brain.tools.phrase_map import match_phrase
from jarvis_brain.tools.watchdog import Watchdog, in_quiet_hours, parse_quiet_window
from jarvis_brain.vision.regions import match_region, regions_from_text
from jarvis_brain.vision.service import ScreenShot, VisionService


class FakeHermes:
    async def ping(self):
        return {"ok": True}

    async def chat_stream(self, session_id, user_text, *, instructions):
        yield StreamEvent("assistant.delta", {"delta": "ok"})
        yield StreamEvent("run.completed", {"ok": True})


def _client(**kwargs) -> TestClient:
    bus = kwargs.pop("bus", EventBus())
    runtime = ProductRuntime(
        cfg=BrainConfig(),
        bus=bus,
        hermes=kwargs.pop("hermes", FakeHermes()),  # type: ignore[arg-type]
        tts=None,
        session_id="s-r4",
        **kwargs,
    )
    return TestClient(attach_product_routes(bus.app(), runtime)), runtime


def test_phrases_round4() -> None:
    assert match_phrase("pon el overlay").action == "hud.overlay"
    assert match_phrase("pon el overlay").payload["enabled"] is True
    assert match_phrase("quita el overlay").payload["enabled"] is False
    assert match_phrase("pon el visor").action == "hud.visor"
    assert match_phrase("instala la voz").action == "voice.install"
    assert match_phrase("clica en Docs").action == "vision.click"
    assert match_phrase("mapa de la casa").action == "ha.schematic"
    assert match_phrase("otro feed").payload["id"] == "next"
    assert match_phrase("jwst").payload["id"] == "jwst"
    assert match_phrase("pon el feed vivo").payload["id"] == "iss"


def test_quiet_hours_and_profile() -> None:
    assert parse_quiet_window("23:00-07:00") is not None
    night = datetime(2026, 9, 5, 23, 30)
    noon = datetime(2026, 9, 5, 12, 0)
    assert in_quiet_hours(night, "23:00-07:00") is True
    assert in_quiet_hours(noon, "23:00-07:00") is False
    dog = Watchdog()
    assert dog.load_max > 0


def test_lexical_ranks_without_ollama() -> None:
    assert lexical_score("pop os", "el taller es Pop OS") > 0.3
    hits = rank_texts(
        "pop",
        [{"text": "el taller es Pop OS", "id": "1"}, {"text": "otra cosa", "id": "2"}],
    )
    assert hits[0]["text"].startswith("el taller")


def test_layered_lexical_backend(tmp_path) -> None:
    local = LocalMemory(tmp_path / "m.jsonl")
    layered = LayeredMemory(local, None)
    layered.add("Dario en Pop OS", role="fact")
    hits = layered.search("popos")
    assert hits
    assert layered.backend == "jsonl+lexical"


def test_schematic_zones() -> None:
    data = build_schematic(
        [
            {"entity_id": "light.cocina", "state": "on", "name": "Cocina"},
            {"entity_id": "lock.puerta", "state": "locked", "name": "Puerta"},
        ]
    )
    luces = next(z for z in data["zones"] if z["id"] == "luces")
    assert luces["on"] == 1
    client, _ = _client()
    body = client.get("/api/ha/schematic").json()
    assert body["ok"] is True
    assert len(body["zones"]) == 4


def test_regions_and_click_phrase() -> None:
    regions = regions_from_text("Docs https://example.com/x", width=100, height=100)
    assert match_region(regions, "docs")
    buf = BytesIO()
    Image.new("RGB", (32, 24), (8, 8, 8)).save(buf, format="PNG")
    vis = VisionService()
    vis.last_shot = ScreenShot(
        text="ocr",
        ocr="Docs https://example.com/x",
        fingerprint="0",
        backend="test",
        width=32,
        height=24,
        changed=True,
        jpeg=buf.getvalue(),
        regions=regions,
    )
    gate = AuthGate(compare=None, user="dario")
    client, _ = _client(auth=gate, vision=vis)
    denied = client.post("/api/vision/click", json={"text": "Docs"})
    assert denied.status_code == 403
    chat = client.post("/api/chat", json={"message": "clica en Docs"})
    assert chat.status_code == 200
    assert "Howdy" in chat.json()["reply"]


def test_overlay_and_welcome() -> None:
    client, runtime = _client()
    on = client.post("/api/hud/overlay", json={"enabled": True})
    assert on.json()["overlay"] is True
    client.post("/api/hud/presence", json={"present": False})
    back = client.post("/api/hud/presence", json={"present": True})
    assert back.json()["presence"] is True
    assert runtime.hud.toasts
    assert any("Bienvenido" in str(t.get("content")) for t in runtime.hud.toasts)


def test_second_live_and_next() -> None:
    client, runtime = _client()
    data = client.get("/api/map").json()
    ids = [f["id"] for f in data["live"]]
    assert "iss" in ids
    assert "jwst" in ids
    assert len(data["live"]) <= 2
    first = client.post("/api/chat", json={"message": "pon el feed vivo"})
    assert first.status_code == 200
    assert runtime.world.last_selection["feed_id"] == "iss"
    nxt = client.post("/api/chat", json={"message": "otro feed"})
    assert nxt.status_code == 200
    assert runtime.world.last_selection["feed_id"] == "jwst"


def test_surv_contract_and_tick() -> None:
    client, _ = _client()
    snap = client.get("/api/surveillance").json()
    assert snap["contract"]["docs"] == "docs/DETECT.md"
    assert "tick" in snap["contract"]["stdin"]
    tick = client.post("/api/surveillance/tick", json={"camera": "door"})
    assert tick.status_code == 200


def test_voice_status_has_install() -> None:
    client, _ = _client()
    body = client.get("/api/voice").json()
    assert "install_stt" in body["install"]
    assert "pcm" in body
    chat = client.post("/api/chat", json={"message": "instala la voz"})
    assert "pip install" in chat.json()["reply"]
