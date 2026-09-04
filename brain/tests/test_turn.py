from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig, build_overlay
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.turn import collect_bus_events, run_text_turn
from jarvis_brain.voice.config import VoiceConfig
from jarvis_brain.voice.tts import LocalTTS


class FakeHermes:
    async def chat_stream(self, session_id, user_text, *, instructions):
        assert "JARVIS_PHASE1_OK" in instructions
        assert session_id == "s1"
        assert user_text == "hola"
        yield StreamEvent("assistant.delta", {"delta": "Acknowledged. "})
        yield StreamEvent("assistant.delta", {"delta": "JARVIS_PHASE1_OK."})
        yield StreamEvent("run.completed", {"ok": True})


async def test_text_turn_publishes_and_joins() -> None:
    bus = EventBus()
    seen = collect_bus_events(bus)
    cfg = BrainConfig(overlay=build_overlay(qa=True))
    reply = await run_text_turn(
        user_text="hola",
        cfg=cfg,
        hermes=FakeHermes(),  # type: ignore[arg-type]
        bus=bus,
        session_id="s1",
    )
    assert "JARVIS_PHASE1_OK" in reply
    types = [e.type for e in seen]
    assert types[0] == "user.text"
    assert "assistant.delta" in types
    assert "assistant.text" in types
    assert "hud.set_mode" in types
    idle = [e for e in seen if e.type == "brain.status" and e.payload.get("state") == "idle"]
    assert idle
    assert seen[-1].type == "hud.set_mode"
    assert seen[-1].payload["operational"] == "standby"


class _Engine:
    name = "fake"
    sample_rate = 24000

    def speak(self, text: str, voice: str) -> bytes:
        return b"\x00\x10" * 24

    def stop(self) -> None:
        return


class BoomHermes:
    async def chat_stream(self, session_id, user_text, *, instructions):
        raise AssertionError("phrase-map must not call Hermes")


async def test_phrase_map_skips_hermes() -> None:
    reply = await run_text_turn(
        user_text="cómo está el sistema",
        cfg=BrainConfig(),
        hermes=BoomHermes(),  # type: ignore[arg-type]
        bus=EventBus(),
        session_id="s1",
    )
    assert reply.startswith("Sistema:")


async def test_text_turn_speaks() -> None:
    bus = EventBus()
    seen = collect_bus_events(bus)
    tts = LocalTTS(VoiceConfig(), engine=_Engine())
    reply = await run_text_turn(
        user_text="hola",
        cfg=BrainConfig(overlay=build_overlay(qa=True)),
        hermes=FakeHermes(),  # type: ignore[arg-type]
        bus=bus,
        session_id="s1",
        tts=tts,
    )
    assert "JARVIS_PHASE1_OK" in reply
    assert any(e.type == "hud.speak" for e in seen)
    assert tts.last_chunk is not None
    assert tts.last_chunk.pcm
