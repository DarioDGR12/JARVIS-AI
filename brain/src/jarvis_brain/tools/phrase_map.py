from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field

from jarvis_brain.map.feeds import resolve_place
from jarvis_brain.tools.stats import format_stats, system_stats


@dataclass(frozen=True)
class PhraseHit:
    action: str
    reply: str
    ran: bool
    payload: dict = field(default_factory=dict)


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
_MAP_OPEN = re.compile(
    r"\b(abre|abrir|muestra|mu[eé]strame|ens[eé][nñ]ame|show|open)\b.+"
    r"\b(mapa|globo|map|globe|sentinel)\b"
    r"|\b(mapa|globo)\b(\s+(por favor|please))?$",
    re.I,
)
_MAP_FOCUS = re.compile(
    r"\b(d[oó]nde est[aá]|enfoca|focus|mira)\b\s+(.+)$",
    re.I,
)
_VISION_CAPTURE = re.compile(
    r"\b(captura(r)?( la)? pantalla|screenshot|qu[eé] hay en (la )?pantalla|"
    r"lee(r)? la pantalla|mira( la)? pantalla|what.?s on (the )?screen)\b",
    re.I,
)
_VISION_CAM_OFF = re.compile(
    r"\b(cierra|apaga|quita|stop|off)\b.+\b(c[aá]mara|webcam|camera)\b",
    re.I,
)
_VISION_CAM_ON = re.compile(
    r"\b(abre|abrir|enciende|prende|muestra|mu[eé]strame|mira|show|open|on)\b"
    r".+\b(c[aá]mara|webcam|camera)\b"
    r"|\b(c[aá]mara|webcam)\b(\s+(por favor|please))?$",
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
    if _VISION_CAPTURE.search(raw):
        return PhraseHit("vision.capture", "Capturando la pantalla.", True)
    if _VISION_CAM_OFF.search(raw):
        return PhraseHit("vision.camera", "Cerrando la cámara.", True, {"enabled": False})
    if _VISION_CAM_ON.search(raw):
        return PhraseHit("vision.camera", "Abriendo la cámara.", True, {"enabled": True})
    if _MAP_OPEN.search(raw):
        return PhraseHit("map.show", "Abriendo el globo.", True)
    focus = _MAP_FOCUS.search(raw)
    if focus:
        place = resolve_place(focus.group(2))
        if place:
            return PhraseHit(
                "map.focus",
                f"Enfocando {place['loc']}.",
                True,
                {"lat": place["lat"], "lon": place["lon"], "zoom": 7, "id": place["id"]},
            )
        return PhraseHit(
            "map.query",
            f"Buscando {focus.group(2).strip()} en el globo.",
            True,
            {"q": focus.group(2).strip()},
        )
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
