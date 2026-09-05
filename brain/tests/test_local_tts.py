from jarvis_brain.bus.envelope import Event
from jarvis_brain.voice.config import VoiceConfig
from jarvis_brain.voice.tts import LocalTTS, PcmChunk


class FakeEngine:
    name = "fake"

    def __init__(self) -> None:
        self.stopped = False
        self.last = ""

    def speak(self, text: str, voice: str) -> bytes:
        self.last = f"{voice}:{text}"
        # 24 kHz native: 24 frames of silence
        return b"\x00\x00" * 24

    def stop(self) -> None:
        self.stopped = True


def test_speak_emits_hud_event_and_resamples() -> None:
    events: list[Event] = []
    chunks: list[tuple[bytes, int]] = []
    tts = LocalTTS(
        VoiceConfig(),
        on_event=events.append,
        on_pcm=lambda pcm, rate: chunks.append((pcm, rate)),
        engine=FakeEngine(),
    )
    out = tts.speak_text("  **Hello.**  ", voice="jarvis")
    assert isinstance(out, PcmChunk)
    assert out.sample_rate == 16000
    assert len(out.pcm) == 16 * 2
    assert events[0].type == "hud.speak"
    assert events[0].payload["text"] == "Hello."
    assert events[0].payload["voice"] == "jarvis"
    assert chunks[0][1] == 16000


def test_stream_joins_deltas() -> None:
    engine = FakeEngine()
    tts = LocalTTS(VoiceConfig(), engine=engine)
    tts.speak_stream(["Sys", "tems ", "online."], voice="companion")
    assert engine.last == "companion:Systems online."


def test_interrupt_stops_engine() -> None:
    engine = FakeEngine()
    tts = LocalTTS(VoiceConfig(), engine=engine)
    tts.speak_text("Again.", interrupt=True)
    assert engine.stopped is True


def test_empty_after_clean_is_silent() -> None:
    tts = LocalTTS(VoiceConfig(), engine=FakeEngine())
    out = tts.speak_text("<think>only</think>")
    assert out.pcm == b""
