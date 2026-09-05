from __future__ import annotations

from jarvis_brain.bus.envelope import Event, new_event


def hud_speak(
    text: str,
    *,
    voice: str,
    interrupt: bool = False,
    viseme: str | None = None,
    corr_id: str | None = None,
) -> Event:
    """Visual-only speak event. PCM travels on the voice websocket, not here."""
    payload = {
        "text": text,
        "voice": voice,
        "interrupt": interrupt,
        "viseme": viseme,
    }
    return new_event("hud.speak", payload, source="voice", corr_id=corr_id)
