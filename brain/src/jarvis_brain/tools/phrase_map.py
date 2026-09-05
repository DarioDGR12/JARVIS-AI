from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field

from jarvis_brain.ha.client import HomeAssistant
from jarvis_brain.map.briefing import brief_world
from jarvis_brain.map.feeds import resolve_place
from jarvis_brain.tools.stats import format_stats, system_stats


@dataclass(frozen=True)
class PhraseHit:
    action: str
    reply: str
    ran: bool
    payload: dict = field(default_factory=dict)
    handoff: bool = False


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
_VISION_EXPLAIN = re.compile(
    r"\b(explica|analiz[ae]|describe)\b.+\b(pantalla|screen)\b|\bqu[eé] ves\b",
    re.I,
)
_VISION_CAPTURE = re.compile(
    r"\b(captura(r)?( la)? pantalla|screenshot|qu[eé] hay en (la )?pantalla|"
    r"lee(r)? la pantalla|mira( la)? pantalla|what.?s on (the )?screen)\b",
    re.I,
)
_VISOR_OFF = re.compile(
    r"\b(quita|apaga|cierra|off)\b.+\bvisor\b",
    re.I,
)
_VISOR_ON = re.compile(
    r"\b(pon|activa|enciende|abre|on)\b.+\b(visor|hud encima)\b"
    r"|\bvisor\b(\s+(por favor|please))?$",
    re.I,
)
_OVERLAY_OFF = re.compile(
    r"\b(quita|apaga|cierra|off)\b.+\boverlay\b",
    re.I,
)
_OVERLAY_ON = re.compile(
    r"\b(pon|activa|enciende|abre|on)\b.+\boverlay\b"
    r"|\boverlay\b(\s+(por favor|please))?$",
    re.I,
)
_VOICE_INSTALL = re.compile(
    r"\b(instala|instalar|pon)\b.+\b(voz local|stt local|whisper|wake ?word)\b"
    r"|\binstala la voz\b",
    re.I,
)
_VISION_CLICK = re.compile(
    r"\b(clica|clic[aá]?|haz clic|click|pulsa)\b(?:\s+en)?\s+(.+)$",
    re.I,
)
_VISION_TYPE = re.compile(
    r"\b(escribe|teclea|type)\b\s+(.+?)\s+\ben\s+(.+)$",
    re.I,
)
_GESTURE_PINCH = re.compile(r"\b(pellizca|pellizco|pinch)\b", re.I)
_GESTURE_SPREAD = re.compile(
    r"\b(abre las manos|abre la mano|separa las manos|spread)\b",
    re.I,
)
_HA_SCHEMATIC = re.compile(
    r"\b(mapa de (la )?casa|esquema( de (la )?casa)?|schematic)\b",
    re.I,
)
_LIVE_NEXT = re.compile(
    r"\b(otro feed|siguiente (feed|directo)|cambia( el)? (feed|directo))\b",
    re.I,
)
_REMEMBER = re.compile(r"^\s*(recuerda|remember)(?:\s+que)?\s+(.+)$", re.I)
_FORGET = re.compile(r"^\s*(olvida|forget)(?:\s+que)?\s+(.+)$", re.I)
_HA_STATUS = re.compile(
    r"\b(c[oó]mo est[aá] la casa|estado de (la )?casa|home status)\b",
    re.I,
)
_BRIEF_WORLD = re.compile(
    r"\b(briefing|informe del mundo|qu[eé] pasa en el mundo|world brief)\b",
    re.I,
)
_BRIEF_PLACE = re.compile(
    r"\b(qu[eé] pasa en|informe de|briefing de)\s+(.+)$",
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
_VISION_OPEN = re.compile(
    r"\b(abre|abrir|open)\b.+\b(enlace|enlaces|url|urls|link|links)\b"
    r"|\b(abre ese link|abre la url)\b",
    re.I,
)
_RECALL = re.compile(
    r"\b(qu[eé] recuerdas|qu[eé] sabes de m[ií]|lista (de )?recuerdos|"
    r"what do you remember)\b",
    re.I,
)
_HA_SCENE = re.compile(
    r"\b(?:activa(?:r)?|enciende|pon|lanza)\b.+\bescena\s+(.+)$"
    r"|\bescena\s+(.+)$"
    r"|\bscene\s+(.+)$",
    re.I,
)
_CLICK_THROUGH_OFF = re.compile(
    r"\b(captura (los )?clics|deja de atravesar|sin click.?through)\b",
    re.I,
)
_LIVE_FEED = re.compile(
    r"\b(feed vivo|directo de la nasa|nasa tv|pon el (feed|directo)|abre (el )?iss|"
    r"qu[eé] hay en la iss|nasa plus|cosmic dawn|jwst)\b"
    r"|\biss\b(\s+(por favor|please))?$",
    re.I,
)
_CLICK_THROUGH_ON = re.compile(
    r"\b(deja pasar( los)? clics|atraviesa|click.?through|ignora (los )?clics)\b",
    re.I,
)


def scene_entity(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", (name or "").strip().lower()).strip("_")
    return f"scene.{slug or 'noche'}"


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
    if _HA_STATUS.search(raw):
        return PhraseHit("ha.status", HomeAssistant().status_line(), True)
    remember = _REMEMBER.match(raw)
    if remember:
        fact = remember.group(2).strip()
        return PhraseHit("memory.add", f"Anotado: {fact}", True, {"text": fact})
    forget = _FORGET.match(raw)
    if forget:
        fact = forget.group(2).strip()
        return PhraseHit("memory.forget", f"Olvidando: {fact}", True, {"query": fact})
    if _RECALL.search(raw):
        return PhraseHit("memory.list", "Repasando hechos.", True)
    if _CLICK_THROUGH_OFF.search(raw):
        return PhraseHit("hud.click_through", "Clics de vuelta al visor.", True, {"enabled": False})
    if _CLICK_THROUGH_ON.search(raw):
        return PhraseHit(
            "hud.click_through",
            "Clics atraviesan. Di «captura los clics» o usa la bandeja.",
            True,
            {"enabled": True},
        )
    scene = _HA_SCENE.search(raw)
    if scene:
        name = (scene.group(1) or scene.group(2) or scene.group(3) or "").strip()
        if name:
            entity = scene_entity(name)
            return PhraseHit(
                "ha.scene",
                f"Activando {entity}.",
                True,
                {"entity_id": entity, "name": name},
            )
    if _VISION_OPEN.search(raw):
        return PhraseHit("vision.open", "Abriendo enlaces de la pantalla.", True)
    typed = _VISION_TYPE.search(raw)
    if typed:
        text = typed.group(2).strip().strip("\"'")
        target = typed.group(3).strip()
        return PhraseHit(
            "vision.type",
            f"Escribiendo {text} en {target}.",
            True,
            {"text": text, "query": target},
        )
    if _GESTURE_PINCH.search(raw):
        return PhraseHit(
            "hud.gesture",
            "Pellizco.",
            True,
            {"name": "pinch", "hand": "both", "confidence": 0.95},
        )
    if _GESTURE_SPREAD.search(raw):
        return PhraseHit(
            "hud.gesture",
            "Manos abiertas.",
            True,
            {"name": "spread", "hand": "both", "confidence": 0.95},
        )
    click = _VISION_CLICK.search(raw)
    if click:
        target = click.group(2).strip()
        return PhraseHit("vision.click", f"Clic en {target}.", True, {"text": target})
    if _HA_SCHEMATIC.search(raw):
        return PhraseHit("ha.schematic", "Esquema de la casa.", True)
    if _VOICE_INSTALL.search(raw):
        return PhraseHit(
            "voice.install",
            "En Pop!_OS: cd brain && ./scripts/install_stt.sh "
            "(pip install -e '.[stt]'). Sin mic, el HUD sigue en Web Speech.",
            True,
        )
    if _OVERLAY_OFF.search(raw):
        return PhraseHit("hud.overlay", "Overlay off.", True, {"enabled": False})
    if _OVERLAY_ON.search(raw):
        return PhraseHit("hud.overlay", "Overlay on.", True, {"enabled": True})
    if _VISOR_OFF.search(raw):
        return PhraseHit("hud.visor", "Visor off.", True, {"enabled": False})
    if _VISOR_ON.search(raw):
        return PhraseHit("hud.visor", "Visor on.", True, {"enabled": True})
    if _LIVE_NEXT.search(raw):
        return PhraseHit("map.live", "Siguiente feed vivo.", True, {"id": "next"})
    if _LIVE_FEED.search(raw):
        feed_id = "jwst" if re.search(r"jwst|cosmic|nasa plus", raw, re.I) else "iss"
        return PhraseHit(
            "map.live",
            "Abriendo el feed vivo.",
            True,
            {"id": feed_id},
        )
    if _BRIEF_WORLD.search(raw):
        text = brief_world(None)
        return PhraseHit("map.brief", text, True, {"q": ""})
    brief = _BRIEF_PLACE.search(raw)
    if brief:
        q = brief.group(2).strip()
        if q.lower() not in {"el mundo", "mundo", "the world"}:
            text = brief_world(q)
            return PhraseHit("map.brief", text, True, {"q": q})
    if _VISION_EXPLAIN.search(raw):
        return PhraseHit(
            "vision.explain",
            "Mirando la pantalla.",
            True,
            {},
            handoff=True,
        )
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
