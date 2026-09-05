import asyncio
import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from jarvis_brain.auth.howdy import AuthGate, warm_howdy
from jarvis_brain.bus.envelope import new_event
from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.ha.client import HAConfig
from jarvis_brain.ha.rooms import infer_room, group_rooms
from jarvis_brain.ha.schematic import build_schematic
from jarvis_brain.ha.ws import HAWebsocket, ws_url
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.hud.state import HudState
from jarvis_brain.product.app import ProductRuntime, attach_product_routes
from jarvis_brain.tools.phrase_map import match_phrase
from jarvis_brain.tools.watchdog import officer_may_speak
from jarvis_brain.vision.service import ScreenShot, VisionService
from jarvis_brain.vision.typewrite import type_text
from jarvis_brain.voice.config import resolve_voice_wav


class FakeHermes:
    async def ping(self):
        return {"ok": True}

    async def chat_stream(self, session_id, user_text, *, instructions):
        yield StreamEvent("assistant.delta", {"delta": "ok"})
        yield StreamEvent("run.completed", {"ok": True})


def _client(**kwargs) -> tuple[TestClient, ProductRuntime]:
    bus = kwargs.pop("bus", EventBus())
    runtime = ProductRuntime(
        cfg=BrainConfig(),
        bus=bus,
        hermes=kwargs.pop("hermes", FakeHermes()),  # type: ignore[arg-type]
        tts=None,
        session_id="s-r5",
        **kwargs,
    )
    return TestClient(attach_product_routes(bus.app(), runtime)), runtime


def test_phrases_round5() -> None:
    pinch = match_phrase("pellizca")
    assert pinch and pinch.action == "hud.gesture"
    assert pinch.payload["name"] == "pinch"
    spread = match_phrase("abre las manos")
    assert spread and spread.payload["name"] == "spread"
    typed = match_phrase("escribe hola en Docs")
    assert typed and typed.action == "vision.type"
    assert typed.payload["text"] == "hola"
    assert typed.payload["query"] == "Docs"
    assert match_phrase("pon el overlay").action == "hud.overlay"
    assert match_phrase("captura los clics").action == "hud.click_through"


def test_officer_silent_when_seat_empty() -> None:
    hud = HudState()
    assert officer_may_speak(hud) is True
    hud.apply(new_event("hud.presence", {"present": False}, source="hud"))
    assert hud.standby_empty is True
    assert officer_may_speak(hud) is False


def test_rooms_from_entity_ids() -> None:
    rooms = group_rooms(
        [
            {"entity_id": "light.cocina_techo", "state": "on", "name": "Techo"},
            {"entity_id": "light.otro", "state": "off", "name": "Otro"},
        ]
    )
    ids = {r["id"] for r in rooms}
    assert "cocina" in ids
    assert infer_room("light.living_room_lamp") == "salon"
    data = build_schematic(
        [
            {"entity_id": "light.cocina_techo", "state": "on", "name": "Techo"},
            {"entity_id": "lock.puerta", "state": "locked", "name": "Puerta"},
        ]
    )
    assert data["rooms"]
    assert any(r["id"] == "cocina" for r in data["rooms"])


def test_gesture_and_type_routes() -> None:
    from jarvis_brain.vision.regions import regions_from_text

    regions = regions_from_text("Docs https://example.com/x", width=100, height=100)
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
    client, runtime = _client(auth=gate, vision=vis)
    g = client.post("/api/hud/gesture", json={"name": "pinch", "hand": "both"})
    assert g.status_code == 200
    assert runtime.hud.last_gesture["name"] == "pinch"
    denied = client.post("/api/vision/type", json={"query": "Docs", "text": "hola"})
    assert denied.status_code == 403
    chat = client.post("/api/chat", json={"message": "escribe hola en Docs"})
    assert chat.status_code == 200
    assert "Howdy" in chat.json()["reply"]
    zoom = client.post("/api/chat", json={"message": "pellizca"})
    assert zoom.status_code == 200
    assert runtime.hud.last_gesture["name"] == "pinch"


def test_type_record_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_VISION_TYPE", raising=False)
    monkeypatch.delenv("JARVIS_VISION_CLICK", raising=False)
    out = type_text("hola", {"text": "Docs"})
    assert out["typed"] is False
    assert out["reason"] == "record-only"


def test_howdy_warm_never_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_PRESENCE_HOWDY", raising=False)
    gate = AuthGate(compare=None, user="dario")
    assert warm_howdy(gate)["reason"] == "flag-off"
    monkeypatch.setenv("JARVIS_PRESENCE_HOWDY", "1")
    assert warm_howdy(gate)["reason"] == "not-enrolled"


def test_voice_wav_defaults_to_repo() -> None:
    path = resolve_voice_wav("jarvis")
    assert path
    assert Path(path).is_file()
    assert Path(path).name == "jarvis.wav"


def test_ha_ws_url() -> None:
    assert ws_url("http://homeassistant.local:8123") == "ws://homeassistant.local:8123/api/websocket"
    assert ws_url("https://ha.example") == "wss://ha.example/api/websocket"
    snap = HAWebsocket(HAConfig(url="", token="")).snapshot()
    assert snap["connected"] is False
    client_src = Path(__file__).resolve().parents[1] / "src/jarvis_brain/ha/client.py"
    assert "/api/services/" in client_src.read_text()
    assert 'f"{self.cfg.url}/api/states"' not in client_src.read_text().split("def call")[1]


@pytest.mark.asyncio
async def test_ha_websocket_subscribe() -> None:
    import websockets

    got = {}

    async def handler(ws):
        await ws.send(json.dumps({"type": "auth_required", "ha_version": "2024.1"}))
        auth = json.loads(await ws.recv())
        assert auth["type"] == "auth"
        assert auth["access_token"] == "tok"
        await ws.send(json.dumps({"type": "auth_ok"}))
        sub = json.loads(await ws.recv())
        assert sub["type"] == "subscribe_events"
        assert sub["event_type"] == "state_changed"
        await ws.send(json.dumps({"id": sub["id"], "type": "result", "success": True}))
        await ws.send(
            json.dumps(
                {
                    "type": "event",
                    "event": {
                        "event_type": "state_changed",
                        "data": {
                            "entity_id": "light.x",
                            "new_state": {"state": "on"},
                            "old_state": {"state": "off"},
                        },
                    },
                }
            )
        )
        await asyncio.sleep(0.2)

    async with websockets.serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = HAWebsocket(HAConfig(url=f"http://127.0.0.1:{port}", token="tok"))

        async def on_event(payload):
            got.update(payload)
            client.stop()

        await asyncio.wait_for(client.run(on_event), timeout=4)
    assert got.get("entity_id") == "light.x"
    assert got.get("new_state") == "on"
    assert client.connected or client.last_event


def test_status_exposes_ha_ws() -> None:
    client, _ = _client()
    body = client.get("/api/status").json()
    assert "ws" in body["ha"]
    assert body["ha"]["ws"]["connected"] is False
    mem = client.get("/api/memory").json()
    assert mem["onnx"]["enabled"] is False


def test_packaging_files_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    assert (root / "deploy" / "systemd" / "jarvis-brain.service").is_file()
    assert (root / "deploy" / "systemd" / "jarvis-door.service").is_file()
    assert (root / "deploy" / "kiosk" / "jarvis-kiosk.sh").is_file()
    assert (root / "scripts" / "install-user.sh").is_file()
    assert (root / "voices" / "README.md").is_file()
    assert (root / "desktop" / "ui" / "gestures.js").is_file()
