import importlib.util
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from jarvis_brain.auth.howdy import AuthGate
from jarvis_brain.bus.envelope import new_event
from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.ha.client import HAConfig, HomeAssistant
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.hud.state import HudState
from jarvis_brain.map.weather import attach_weather, format_current
from jarvis_brain.memory.store import LocalMemory
from jarvis_brain.product.app import ProductRuntime, attach_product_routes
from jarvis_brain.tools.phrase_map import match_phrase, scene_entity
from jarvis_brain.tools.watchdog import Watchdog
from jarvis_brain.turn import run_text_turn
from jarvis_brain.vision.service import ScreenShot, VisionService
from jarvis_brain.vision.urls import extract_urls


class FakeHermes:
    async def ping(self):
        return {"ok": True}

    async def chat_stream(self, session_id, user_text, *, instructions):
        yield StreamEvent("assistant.delta", {"delta": "ok"})
        yield StreamEvent("run.completed", {"ok": True})


class DownHermes:
    async def ping(self):
        raise RuntimeError("hermes down")

    async def chat_stream(self, session_id, user_text, *, instructions):
        yield StreamEvent("error", {"message": "down"})


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (32, 24), (8, 8, 8)).save(buf, format="PNG")
    return buf.getvalue()


def _client(**kwargs) -> TestClient:
    bus = kwargs.pop("bus", EventBus())
    runtime = kwargs.pop("runtime", None) or ProductRuntime(
        cfg=BrainConfig(),
        bus=bus,
        hermes=kwargs.pop("hermes", FakeHermes()),  # type: ignore[arg-type]
        tts=None,
        session_id="s-r2",
        **kwargs,
    )
    return TestClient(attach_product_routes(bus.app(), runtime)), runtime


def test_phrases_round2() -> None:
    assert match_phrase("qué recuerdas").action == "memory.list"
    assert match_phrase("abre el enlace").action == "vision.open"
    assert match_phrase("escena noche").action == "ha.scene"
    assert match_phrase("escena noche").payload["entity_id"] == "scene.noche"
    assert scene_entity("Buenas Noches") == "scene.buenas_noches"
    assert match_phrase("deja pasar los clics").action == "hud.click_through"
    assert match_phrase("deja pasar los clics").payload["enabled"] is True
    assert match_phrase("captura los clics").payload["enabled"] is False


def test_extract_urls_http_only() -> None:
    text = "mira https://example.com/x y file:///etc/passwd y http://127.0.0.1:8765/ok"
    urls = extract_urls(text)
    assert urls == ["https://example.com/x", "http://127.0.0.1:8765/ok"]


def test_weather_format_and_attach() -> None:
    line = format_current(
        {"current": {"temperature_2m": 18.4, "weather_code": 2}},
        lat=35.67,
        lon=139.65,
    )
    assert line and "18 °C" in line and "nublado" in line
    brief = attach_weather("Briefing Tokio", "Tokio", fetch=lambda lat, lon: f"wx {lat:.1f}")
    assert "wx 35.7" in brief
    offline = attach_weather("Briefing Tokio", "Tokio", fetch=lambda *_: None)
    assert offline == "Briefing Tokio"


def test_list_facts_and_recall(tmp_path) -> None:
    mem = LocalMemory(tmp_path / "m.jsonl")
    mem.add("chat ruido", role="user")
    mem.add("Dario usa Pop", role="fact")
    facts = mem.list_facts()
    assert len(facts) == 1
    assert facts[0]["text"] == "Dario usa Pop"
    client, _ = _client(memory=mem)
    r = client.post("/api/chat", json={"message": "qué recuerdas"})
    assert r.status_code == 200
    assert "Dario usa Pop" in r.json()["reply"]
    listed = client.get("/api/memory", params={"facts": True})
    assert listed.json()["items"][0]["text"] == "Dario usa Pop"


def test_scene_and_open_need_howdy() -> None:
    gate = AuthGate(compare=None, user="dario")
    ha = HomeAssistant(HAConfig(url="http://127.0.0.1:18123", token="x"))
    vis = VisionService()
    vis.last_shot = ScreenShot(
        text="ocr",
        ocr="lee https://example.com/docs",
        fingerprint="0",
        backend="test",
        width=10,
        height=10,
        changed=True,
        jpeg=_png(),
    )
    client, _ = _client(auth=gate, ha=ha, vision=vis)
    scene = client.post("/api/chat", json={"message": "escena noche"})
    assert scene.status_code == 200
    assert "Howdy" in scene.json()["reply"]
    opened = client.post("/api/chat", json={"message": "abre el enlace"})
    assert opened.status_code == 200
    assert "Howdy" in opened.json()["reply"]
    api = client.post("/api/vision/open", json={})
    assert api.status_code == 403


async def test_officer_hermes_down() -> None:
    bus = EventBus()
    runtime = ProductRuntime(
        cfg=BrainConfig(),
        bus=bus,
        hermes=DownHermes(),  # type: ignore[arg-type]
        tts=None,
        session_id="s-r2",
        watchdog=Watchdog(cooldown_s=999),
    )
    first = await runtime.officer_tick()
    second = await runtime.officer_tick()
    assert first and first[0]["id"] == "hermes"
    assert second == []


def test_presence_standby_and_click_through() -> None:
    client, runtime = _client()
    gone = client.post("/api/hud/presence", json={"present": False})
    assert gone.status_code == 200
    body = gone.json()
    assert body["presence"] is False
    assert body["standby_empty"] is True
    assert body["operational"] == "standby"
    assert runtime.hud.camera_enabled is False
    through = client.post("/api/hud/click-through", json={"enabled": True})
    assert through.json()["click_through"] is True
    off = client.post("/api/hud/visor", json={"enabled": False})
    assert off.json()["click_through"] is False


def test_surv_protocol_and_ingest_script() -> None:
    client, _ = _client()
    snap = client.get("/api/surveillance").json()
    assert snap["ingest"] == "POST /api/surveillance/alert"
    assert "camera" in snap["fields"]
    alert = client.post(
        "/api/surveillance/alert",
        json={"kind": "person", "camera": "door", "score": 0.8, "text": "visita"},
    )
    assert alert.json()["kind"] == "person"
    script = Path(__file__).resolve().parents[1] / "scripts" / "surv_ingest.py"
    spec = importlib.util.spec_from_file_location("surv_ingest", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "surveillance/alert" in (mod.__doc__ or "")


def test_hud_presence_event_standby() -> None:
    hud = HudState()
    hud.apply(new_event("hud.set_mode", {"operational": "boot"}, source="brain"))
    hud.apply(new_event("hud.presence", {"present": False}, source="hud"))
    assert hud.operational == "standby"
    assert hud.standby_empty is True
    hud.apply(new_event("hud.click_through", {"enabled": True}, source="hud"))
    assert hud.click_through is True
    hud.apply(new_event("hud.visor", {"enabled": False}, source="brain"))
    assert hud.click_through is False


async def test_open_without_urls() -> None:
    bus = EventBus()
    reply = await run_text_turn(
        user_text="abre el enlace",
        cfg=BrainConfig(),
        hermes=FakeHermes(),  # type: ignore[arg-type]
        bus=bus,
        session_id="s-r2",
        vision=VisionService(),
    )
    assert "No hay URLs" in reply
