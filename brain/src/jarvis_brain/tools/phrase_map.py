from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass

from jarvis_brain.tools.stats import format_stats, system_stats


@dataclass(frozen=True)
class PhraseHit:
    action: str
    reply: str
    ran: bool


_VOLUME_UP = re.compile(
    r"\b(sube|subir|aumenta|más)\b.*\b(volumen|volume)\b|\bvolume\s*up\b",
    re.I,
)
_VOLUME_DOWN = re.compile(
    r"\b(baja|bajar|baja\s+el|menos)\b.*\b(volumen|volume)\b|\bvolume\s*down\b",
    re.I,
)
_MUTE = re.compile(r"\b(silencio|mute|callate|cállate)\b", re.I)
_LOCK = re.compile(
    r"\b(bloquea|bloquear|lock)\b.*\b(sesi[oó]n|session|pantalla|screen)\b"
    r"|\b(lock\s+(the\s+)?(screen|session))\b",
    re.I,
)
_STATS = re.compile(
    r"\b(c[oó]mo est[aá] el sistema|estado del sistema|system stats|carga del sistema)\b",
    re.I,
)


def _run(cmd: list[str]) -> bool:
    try:
        return subprocess.run(cmd, timeout=3, capture_output=True).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _volume(delta: str) -> bool:
    if shutil.which("wpctl"):
        return _run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", delta])
    if shutil.which("pactl"):
        return _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", delta])
    return False


def _mute() -> bool:
    if shutil.which("wpctl"):
        return _run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
    if shutil.which("pactl"):
        return _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
    return False


def _lock() -> bool:
    if shutil.which("loginctl"):
        return _run(["loginctl", "lock-session"])
    return False


def match_phrase(text: str) -> PhraseHit | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if _STATS.search(raw):
        return PhraseHit("system.stats", format_stats(system_stats()), True)
    if _LOCK.search(raw):
        ok = _lock()
        return PhraseHit(
            "session.lock",
            "Sesión bloqueada." if ok else "No pude bloquear la sesión.",
            ok,
        )
    if _VOLUME_UP.search(raw):
        ok = _volume("5%+")
        return PhraseHit(
            "volume.up",
            "Volumen arriba." if ok else "No hay control de volumen en este equipo.",
            ok,
        )
    if _VOLUME_DOWN.search(raw):
        ok = _volume("5%-")
        return PhraseHit(
            "volume.down",
            "Volumen abajo." if ok else "No hay control de volumen en este equipo.",
            ok,
        )
    if _MUTE.search(raw) and len(raw.split()) <= 4:
        ok = _mute()
        return PhraseHit(
            "volume.mute",
            "Silencio conmutado." if ok else "No hay control de silencio en este equipo.",
            ok,
        )
    return None
