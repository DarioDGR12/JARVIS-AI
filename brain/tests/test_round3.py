import base64
from pathlib import Path

from fastapi.testclient import TestClient

from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.map.feeds import normalize_feed
from jarvis_brain.memory.layered import LayeredMemory
from jarvis_brain.memory.mem0_local import local_mem0_config, ollama_up
from jarvis_brain.memory.store import LocalMemory
from jarvis_brain.product.app import ProductRuntime, attach_product_routes
from jarvis_brain.surveillance.child import DetectorChild
from jarvis_brain.tools.phrase_map import match_phrase
from jarvis_brain.voice.inbound import engine_status
from jarvis_brain.voice.local_engine import LocalVoiceEngine


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
        session_id="s-r3",
        **kwargs,
    )
    return TestClient(attach_product_routes(bus.app(), runtime)), runtime


def test_phrases_round3() -> None:
    assert match_phrase("pon el feed vivo").action == "map.live"
    assert match_phrase("nasa tv").action == "map.live"
    assert match_phrase("iss").payload["id"] == "iss"


def test_local_voice_fake_pcm() -> None:
    saw = {"wake": 0}

    def wake(pcm: bytes, rate: int) -> bool:
        saw["wake"] += 1
        return True

    def stt(pcm: bytes, rate: int) -> str:
        return "hola dario"

    engine = LocalVoiceEngine(wake=wake, stt=stt)
    first = engine.ingest_pcm(b"\x00\x00" * 100, 16000)
    assert first and first["kind"] == "wake"
    # fill ~1.5s buffer
    second = engine.ingest_pcm(b"\x00\x00" * (16000 * 2), 16000)
    assert second and second["kind"] == "transcript"
    assert second["text"] == "hola dario"
    status = engine_status(engine)
    assert status["wake"] == "test"
    assert status["stt"] == "test"
    assert status["hud"]["stt"] == "web-speech"


def test_voice_pcm_api() -> None:
    engine = LocalVoiceEngine(wake=lambda *_: True, stt=lambda *_: "sistema")
    client, _ = _client(voice_engine=engine)
    pcm = base64.b64encode(b"\x00\x00" * 80).decode("ascii")
    wake = client.post("/api/voice/pcm", json={"pcm_b64": pcm, "sample_rate": 16000})
    assert wake.status_code == 200
    assert wake.json()["hit"]["kind"] == "wake"
    body = client.get("/api/voice").json()
    assert body["local"]["loaded"] is True


def test_mem0_config_is_local(tmp_path: Path) -> None:
    cfg = local_mem0_config(tmp_path)
    assert cfg["vector_store"]["provider"] == "qdrant"
    assert "qdrant" in cfg["vector_store"]["config"]["path"]
    assert cfg["llm"]["provider"] == "ollama"
    assert cfg["embedder"]["provider"] == "ollama"
    assert cfg["embedder"]["config"]["embedding_dims"] == 768
    assert ollama_up(timeout_s=0.2) in {True, False}


def test_layered_memory_complements(tmp_path: Path) -> None:
    class FakeMem0:
        def __init__(self) -> None:
            self.added: list[str] = []

        def add(self, text: str) -> None:
            self.added.append(text)

        def search(self, query: str, k: int = 5) -> list[dict]:
            return [{"id": "m1", "text": "hecho remoto " + query, "score": 0.9, "role": "fact"}]

        def forget(self, *, query: str | None = None, id: str | None = None) -> int:
            return 0

    local = LocalMemory(tmp_path / "m.jsonl")
    layered = LayeredMemory(local, FakeMem0())  # type: ignore[arg-type]
    layered.add("Dario en Pop", role="fact")
    hits = layered.search("Pop")
    texts = [h["text"] for h in hits]
    assert any("Pop" in t for t in texts)
    assert any("remoto" in t for t in texts)
    assert layered.backend == "mem0+jsonl"


def test_live_feed_in_catalog() -> None:
    raw = {
        "id": "iss",
        "loc": "NASA TV / ISS",
        "country": "ISS",
        "lat": 27.5,
        "lon": -80.55,
        "hls": "https://ntv1.akamaized.net/hls/live/2014075/NASA-NTV1-HLS/master.m3u8",
        "tags": ["live"],
    }
    feed = normalize_feed(raw)
    assert feed and feed["live"] is True
    assert feed["hls"].startswith("https://ntv1.")
    client, runtime = _client()
    data = client.get("/api/map").json()
    assert data["live"]
    assert data["live"][0]["id"] == "iss"
    live = client.post("/api/chat", json={"message": "pon el feed vivo"})
    assert live.status_code == 200
    assert runtime.world.last_selection
    assert runtime.world.last_selection.get("feed_id") == "iss"


def test_yolo_child_stub(tmp_path: Path) -> None:
    stub = Path(__file__).resolve().parents[1] / "scripts" / "detect_stub.py"
    child = DetectorChild(stub)
    assert child.start() is True
    try:
        hits = child.tick(camera="door")
        assert hits
        assert hits[0]["kind"] == "person"
        assert hits[0]["text"] == "stub person"
    finally:
        child.stop()
    client, runtime = _client()
    snap = client.get("/api/surveillance").json()
    assert snap["policy"] == "yolo-out-of-tree"
    assert "child" in snap
