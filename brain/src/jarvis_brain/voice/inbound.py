from __future__ import annotations

from typing import Any

from jarvis_brain.voice.local_engine import LocalVoiceEngine


def engine_status(engine: LocalVoiceEngine | None = None) -> dict[str, Any]:
    """HUD Web Speech always. Local OWW/whisper when the extras are installed."""
    local = engine.snapshot() if engine is not None else LocalVoiceEngine().snapshot()
    wake = local.get("wake") or "hud-phrase"
    stt = local.get("stt") or "web-speech"
    return {
        "wake": wake,
        "stt": stt,
        "barge_in": True,
        "hud": {"wake": "hud-phrase", "stt": "web-speech"},
        "local": local,
        "note": "Mic HUD + Web Speech. Local = openWakeWord + faster-whisper si están instalados.",
    }
