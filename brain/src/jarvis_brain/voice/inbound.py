from __future__ import annotations

from typing import Any


def engine_status() -> dict[str, Any]:
    """HUD Web Speech. openWakeWord / faster-whisper siguen fuera (ronda 3)."""
    return {
        "wake": "hud-phrase",
        "stt": "web-speech",
        "barge_in": True,
        "note": "Mic HUD + Web Speech API. Barge-in corta el TTS. Modelos locales en ronda 3.",
    }
