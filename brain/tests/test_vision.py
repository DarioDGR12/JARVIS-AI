from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.product.app import ProductRuntime, attach_product_routes
from jarvis_brain.tools.phrase_map import match_phrase
from jarvis_brain.turn import collect_bus_events, run_text_turn
from jarvis_brain.vision.capture import GrabResult, session_type
from jarvis_brain.vision.fingerprint import average_hash, downscale, hamming
from jarvis_brain.vision.service import VisionService


def _png(color: tuple[int, int, int], size: tuple[int, int] = (64, 48)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


class FakeHermes:
    async def ping(self):
        return {"ok": True}

    async def chat_stream(self, session_id, user_text, *, instructions):
        raise AssertionError("vision phrase-map must not call Hermes")


def _client(vision: VisionService | None = None) -> TestClient:
    bus = EventBus()
    runtime = ProductRuntime(
        cfg=BrainConfig(),
        bus=bus,
        hermes=FakeHermes(),  # type: ignore[arg-type]
        tts=None,
        session_id="s-vis",
        vision=vision,
    )
    return TestClient(attach_product_routes(bus.app(), runtime))


def test_fingerprint_stable_and_changes() -> None:
    red = downscale(_png((200, 10, 10)))
    red2 = downscale(_png((200, 10, 10)))
    blue = downscale(_png((10, 10, 200)))
    assert average_hash(red) == average_hash(red2)
    assert hamming(average_hash(red), average_hash(blue)) > 2


def test_capture_once_skips_unchanged() -> None:
    frames = [_png((20, 20, 20)), _png((20, 20, 20)), _png((240, 240, 10))]

    def grab() -> GrabResult:
        return GrabResult(png=frames.pop(0), backend="test", width=64, height=48)

    vis = VisionService(grab=grab)
    a = vis.capture_once()
    b = vis.capture_once()
    c = vis.capture_once()
    assert a.changed is True
    assert b.changed is False
    assert c.changed is True
    assert a.source == "screen"
    assert vis.snapshot()["session"] == session_type()


def test_vision_api_and_watch_gate() -> None:
    vis = VisionService(grab=lambda: GrabResult(png=_png((9, 9, 9)), backend="test", width=64, height=48))
    client = _client(vis)
    status = client.get("/api/status").json()
    assert status["vision"]["source"] == "screen"
    assert status["vision"]["watch"] is False
    cap = client.post("/api/vision/capture", json={"mode": "once"})
    assert cap.status_code == 200
    body = cap.json()
    assert body["ok"] is True
    assert body["source"] == "screen"
    assert body["preview_jpeg_b64"]
    assert client.get("/api/hud").json()["view"] == "vision"
    watch = client.post("/api/vision/watch", json={"enabled": True})
    assert watch.status_code == 403
    assert watch.json()["auth"]["error"] == "no_model"


async def test_phrase_capture_and_camera() -> None:
    assert match_phrase("captura la pantalla").action == "vision.capture"
    assert match_phrase("abre la cámara").action == "vision.camera"
    assert match_phrase("abre la cámara").payload["enabled"] is True
    vis = VisionService(grab=lambda: GrabResult(png=_png((1, 2, 3)), backend="test", width=64, height=48))
    bus = EventBus()
    seen = collect_bus_events(bus)
    reply = await run_text_turn(
        user_text="qué hay en pantalla",
        cfg=BrainConfig(),
        hermes=FakeHermes(),  # type: ignore[arg-type]
        bus=bus,
        session_id="s-vis",
        vision=vis,
    )
    assert "Pantalla" in reply
    types = [e.type for e in seen]
    assert "vision.screen_context" in types
    assert "hud.show_view" in types
