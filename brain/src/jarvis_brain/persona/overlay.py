from __future__ import annotations

import re

from jarvis_brain.config import PERSONALITY_OVERLAY

COMPANION_OVERLAY = (
    "You are JARVIS in the companion register: warmer, still the same assistant. "
    "Answer in 2-4 sentences. Do not mention being an LLM. "
    "Reply in the user's language."
)

_WARM = re.compile(
    r"\b(gracias|por favor|te quiero|c[oó]mo est[aá]s|how are you|"
    r"please|thank you|i miss you|buenos d[ií]as)\b",
    re.I,
)


def choose_persona(text: str) -> str:
    return "companion" if _WARM.search(text or "") else "jarvis"


def persona_overlay(persona: str) -> str:
    if persona == "companion":
        return COMPANION_OVERLAY
    return PERSONALITY_OVERLAY
