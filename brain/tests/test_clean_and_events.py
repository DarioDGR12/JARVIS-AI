from jarvis_brain.voice.clean import clean_for_tts
from jarvis_brain.voice.events import hud_speak


def test_clean_strips_secrets_and_think() -> None:
    raw = "<think>plan</think> Hello. api_key=sk-secret **Sir**"
    assert "sk-secret" not in clean_for_tts(raw)
    assert "think" not in clean_for_tts(raw).lower()
    assert "Hello" in clean_for_tts(raw)
    assert "*" not in clean_for_tts(raw)


def test_hud_speak_is_visual_only() -> None:
    ev = hud_speak("Systems online.", voice="jarvis")
    d = ev.to_dict()
    assert d["v"] == 1
    assert d["type"] == "hud.speak"
    assert d["source"] == "voice"
    assert d["payload"]["text"] == "Systems online."
    assert d["payload"]["voice"] == "jarvis"
    assert "pcm" not in d["payload"]
