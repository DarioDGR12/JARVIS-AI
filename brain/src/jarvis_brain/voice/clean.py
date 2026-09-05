from __future__ import annotations

import re

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_SECRET = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|bearer)\b\s*[:=]\s*\S+"
)
_MD_FENCE = re.compile(r"```.*?```", re.DOTALL)
_MD_MARK = re.compile(r"[*_`#>]{1,3}")


def clean_for_tts(text: str) -> str:
    """Strip think-blocks, secret-shaped lines, and markdown before TTS."""
    if not text:
        return ""
    out = _THINK.sub(" ", text)
    out = _SECRET.sub(" ", out)
    out = _MD_FENCE.sub(" ", out)
    out = _MD_MARK.sub("", out)
    return re.sub(r"\s+", " ", out).strip()


_SENTENCE = re.compile(r"(?<=[.!?…])\s+")


def split_sentences(text: str) -> list[str]:
    """Split cleaned text into speakable sentences."""
    cleaned = clean_for_tts(text)
    if not cleaned:
        return []
    parts = [p.strip() for p in _SENTENCE.split(cleaned) if p.strip()]
    return parts or [cleaned]
