from __future__ import annotations

from typing import Any


def engine_status() -> dict[str, Any]:
    """Ronda 1: contrato. openWakeWord / faster-whisper aún no se cargan aquí."""
    return {
        "wake": "stub",
        "stt": "stub",
        "barge_in": False,
        "note": "POST /api/voice/wake y /api/voice/transcript. Modelos locales en ronda 2.",
    }
