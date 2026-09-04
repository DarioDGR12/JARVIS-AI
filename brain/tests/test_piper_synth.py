from pathlib import Path

import pytest

from jarvis_brain.voice.config import VoiceConfig
from jarvis_brain.voice.tts import LocalTTS, PiperSynthesizer
from jarvis_brain.voice.wav import pcm_rms


def test_piper_requires_model() -> None:
    synth = PiperSynthesizer(VoiceConfig(provider="piper", piper_bin="piper", piper_model=None))
    with pytest.raises(FileNotFoundError):
        synth.speak("hola", "jarvis")


@pytest.mark.skipif(
    not Path.home().joinpath(".local/share/jarvis/piper/piper/piper").is_file(),
    reason="official piper binary not installed",
)
def test_piper_live_speech() -> None:
    tts = LocalTTS(VoiceConfig.from_env())
    assert tts.engine is not None
    assert tts.engine.name == "piper"
    chunk = tts.speak_text("Sistemas en línea.")
    assert chunk.sample_rate == 16000
    assert pcm_rms(chunk.pcm) > 100
    assert len(chunk.pcm) > 16000  # > 0.5 s at 16 kHz mono
