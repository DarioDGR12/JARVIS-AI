from __future__ import annotations

import asyncio

from jarvis_brain.auth.howdy import AuthGate
from jarvis_brain.bus.envelope import Event, new_event
from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.ha.client import HomeAssistant
from jarvis_brain.hermes.client import HermesClient, HermesError
from jarvis_brain.map.weather import attach_weather
from jarvis_brain.memory.store import LocalMemory  # LayeredMemory duck-types this
from jarvis_brain.persona.overlay import choose_persona, persona_overlay
from jarvis_brain.tools.phrase_map import match_phrase
from jarvis_brain.vision.service import VisionService
from jarvis_brain.ha.schematic import build_schematic
from jarvis_brain.vision.click import click_region
from jarvis_brain.vision.regions import match_region
from jarvis_brain.vision.urls import extract_urls, open_urls
from jarvis_brain.voice.tts import LocalTTS, PcmChunk


def _delta_text(event_name: str, data: dict) -> str:
    if event_name in {"assistant.delta", "message.delta"}:
        return str(
            data.get("delta")
            or data.get("text")
            or data.get("content")
            or ""
        )
    if "delta" in data and isinstance(data["delta"], str):
        return data["delta"]
    return ""


async def run_text_turn(
    *,
    user_text: str,
    cfg: BrainConfig,
    hermes: HermesClient,
    bus: EventBus,
    session_id: str,
    overlay: str | None = None,
    tts: LocalTTS | None = None,
    voice: str | None = None,
    memory: LocalMemory | None = None,
    vision: VisionService | None = None,
    auth: AuthGate | None = None,
    ha: HomeAssistant | None = None,
) -> str:
    """One text turn: phrase-map, memory, Hermes, optional speak."""
    persona = choose_persona(user_text)
    voice = voice or persona
    await bus.publish(
        new_event(
            "user.text",
            {"text": user_text, "session_id": session_id, "persona": persona},
            source="cli",
        )
    )
    await bus.publish(
        new_event(
            "hud.set_mode",
            {"operational": "listening", "visual": persona},
            source="brain",
        )
    )
    if persona != "jarvis":
        await bus.publish(
            new_event(
                "persona.changed",
                {"from": "jarvis", "to": persona, "reason": ["warm"], "confidence": 0.7},
                source="brain",
            )
        )
    hit = match_phrase(user_text)
    extra_context = ""
    if hit:
        await bus.publish(
            new_event(
                "tool.local",
                {"action": hit.action, "ran": hit.ran, "session_id": session_id},
                source="brain",
            )
        )
        reply = hit.reply
        if hit.action == "vision.capture" and vision is not None:
            try:
                shot = await asyncio.to_thread(vision.capture_once)
                reply = shot.summary()
                await bus.publish(
                    new_event("vision.screen_context", shot.to_payload(), source="vision")
                )
            except Exception as exc:
                reply = f"No pude capturar la pantalla: {exc}"
                await bus.publish(
                    new_event("vision.error", {"reason": str(exc)}, source="vision")
                )
        elif hit.action == "vision.explain" and vision is not None:
            try:
                shot = await asyncio.to_thread(vision.capture_once)
                extra_context = (
                    f"Screen context ({shot.width}×{shot.height} via {shot.backend}):\n"
                    f"{shot.summary()}\n{shot.ocr}".strip()
                )
                await bus.publish(
                    new_event("vision.screen_context", shot.to_payload(), source="vision")
                )
                await bus.publish(
                    new_event(
                        "hud.highlight",
                        {"target": "screen", "reason": "explain"},
                        source="brain",
                    )
                )
            except Exception as exc:
                extra_context = f"Screen capture failed: {exc}"
                await bus.publish(
                    new_event("vision.error", {"reason": str(exc)}, source="vision")
                )
        elif hit.action == "memory.add" and memory is not None:
            memory.add(str(hit.payload.get("text") or user_text), role="fact")
        elif hit.action == "memory.forget" and memory is not None:
            removed = memory.forget(query=str(hit.payload.get("query") or ""))
            reply = f"Olvidado ({removed})." if removed else "No había nada con eso."
        elif hit.action == "memory.list":
            facts = memory.list_facts() if memory is not None else []
            if not facts:
                reply = "No tengo hechos anotados. Di «recuerda que …»."
            else:
                lines = [f"Recuerdo {len(facts)} hecho(s):"]
                lines.extend(f"- {item['text']}" for item in facts[:12])
                reply = "\n".join(lines)
        elif hit.action == "map.brief":
            reply = attach_weather(reply, str(hit.payload.get("q") or ""))
        elif hit.action == "ha.scene":
            entity = str(hit.payload.get("entity_id") or "")
            if ha is None or not ha.cfg.configured:
                reply = "Casa no configurada. URL y token en la vista Casa."
            elif auth is not None:
                gate = auth.require("ha.command", reason="ha.command")
                if not gate.ok:
                    reply = "Howdy: hace falta cara para escenas."
                    await bus.publish(
                        new_event(
                            "auth.challenge",
                            {"reason": "ha.command", "tool": "ha.command"},
                            source="brain",
                        )
                    )
                    await bus.publish(new_event("auth.result", gate.to_payload(), source="auth"))
                else:
                    try:
                        ha.call("scene", "turn_on", entity_id=entity)
                        reply = f"Escena {entity}."
                    except Exception as exc:
                        reply = f"No pude activar {entity}: {exc}"
            else:
                try:
                    ha.call("scene", "turn_on", entity_id=entity)
                    reply = f"Escena {entity}."
                except Exception as exc:
                    reply = f"No pude activar {entity}: {exc}"
        elif hit.action == "vision.open":
            ocr = vision.last_shot.ocr if vision and vision.last_shot else ""
            urls = extract_urls(ocr)
            if not urls:
                reply = "No hay URLs en la última captura."
            elif auth is not None:
                gate = auth.require("vision.open", reason="vision.open")
                if not gate.ok:
                    reply = "Howdy: hace falta cara para abrir enlaces."
                    await bus.publish(
                        new_event(
                            "auth.challenge",
                            {"reason": "vision.open", "tool": "vision.open"},
                            source="brain",
                        )
                    )
                    await bus.publish(new_event("auth.result", gate.to_payload(), source="auth"))
                else:
                    opened = open_urls(urls)
                    reply = (
                        "Abrí: " + ", ".join(opened)
                        if opened
                        else "xdg-open no disponible."
                    )
            else:
                opened = open_urls(urls)
                reply = (
                    "Abrí: " + ", ".join(opened) if opened else "xdg-open no disponible."
                )
        elif hit.action == "vision.click" and vision is not None:
            regions = (vision.last_shot.regions if vision.last_shot else []) or []
            region = match_region(regions, str(hit.payload.get("text") or ""))
            if not region:
                reply = "No hay región que coincida. Captura la pantalla primero."
            elif auth is not None:
                gate = auth.require("vision.click", reason="vision.click")
                if not gate.ok:
                    reply = "Howdy: hace falta cara para clicar la pantalla."
                    await bus.publish(
                        new_event(
                            "auth.challenge",
                            {"reason": "vision.click", "tool": "vision.click"},
                            source="brain",
                        )
                    )
                    await bus.publish(new_event("auth.result", gate.to_payload(), source="auth"))
                else:
                    result = click_region(region)
                    vision.last_click = result
                    reply = f"Región {region['text']}: {result['reason']}."
            else:
                result = click_region(region)
                vision.last_click = result
                reply = f"Región {region['text']}: {result['reason']}."
            if region:
                await bus.publish(
                    new_event(
                        "hud.highlight",
                        {"target": "screen", "reason": "click", "region": region},
                        source="brain",
                    )
                )
        elif hit.action == "ha.schematic":
            states = []
            if ha is not None and ha.cfg.configured:
                try:
                    raw = ha.states()
                    states = [
                        {
                            "entity_id": s.get("entity_id"),
                            "state": s.get("state"),
                            "name": (s.get("attributes") or {}).get("friendly_name"),
                        }
                        for s in raw
                    ]
                except Exception:
                    states = []
            schematic = build_schematic(states)
            bits = [f"{z['label']} {z['on']}/{z['count']}" for z in schematic["zones"]]
            reply = "Casa: " + (", ".join(bits) if bits else "sin entidades.")
        if hit.handoff:
            await bus.publish(
                new_event("hud.show_view", {"view": "vision", "visible": True}, source="brain")
            )
        else:
            await bus.publish(
                new_event(
                    "assistant.text",
                    {"text": reply, "session_id": session_id, "via": "phrase-map"},
                    source="brain",
                )
            )
            await bus.publish(
                new_event(
                    "hud.display",
                    {"kind": "text", "content": reply, "title": hit.action},
                    source="brain",
                )
            )
            if hit.action in {"map.show", "map.focus", "map.query", "map.brief", "map.live"}:
                await bus.publish(
                    new_event("hud.show_view", {"view": "map", "visible": True}, source="brain")
                )
            if hit.action == "map.focus":
                await bus.publish(new_event("map.focus", hit.payload, source="brain"))
            elif hit.action == "map.query":
                await bus.publish(new_event("map.query", hit.payload, source="brain"))
            elif hit.action == "map.live":
                await bus.publish(new_event("map.live", hit.payload, source="brain"))
            elif hit.action == "vision.capture":
                await bus.publish(
                    new_event("hud.show_view", {"view": "vision", "visible": True}, source="brain")
                )
            elif hit.action == "vision.camera":
                await bus.publish(
                    new_event("hud.show_view", {"view": "vision", "visible": True}, source="brain")
                )
                await bus.publish(
                    new_event(
                        "hud.camera",
                        {"enabled": bool(hit.payload.get("enabled")), "hold": False},
                        source="brain",
                    )
                )
            elif hit.action == "hud.visor":
                await bus.publish(
                    new_event(
                        "hud.visor",
                        {"enabled": bool(hit.payload.get("enabled"))},
                        source="brain",
                    )
                )
            elif hit.action == "hud.overlay":
                await bus.publish(
                    new_event(
                        "hud.overlay",
                        {"enabled": bool(hit.payload.get("enabled"))},
                        source="brain",
                    )
                )
            elif hit.action == "ha.schematic":
                await bus.publish(
                    new_event("hud.show_view", {"view": "ha", "visible": True}, source="brain")
                )
            elif hit.action == "vision.click":
                await bus.publish(
                    new_event("hud.show_view", {"view": "vision", "visible": True}, source="brain")
                )
            elif hit.action == "hud.click_through":
                await bus.publish(
                    new_event(
                        "hud.click_through",
                        {"enabled": bool(hit.payload.get("enabled"))},
                        source="brain",
                    )
                )
            if tts and reply:
                await speak_reply(tts, bus, reply, voice=voice, session_id=session_id)
            await bus.publish(
                new_event(
                    "brain.status",
                    {"state": "idle", "session_id": session_id},
                    source="brain",
                )
            )
            await bus.publish(
                new_event(
                    "hud.set_mode",
                    {"operational": "standby", "visual": persona},
                    source="brain",
                )
            )
            return reply

    facts = memory.overlay_block(user_text) if memory else ""
    if extra_context:
        facts = f"{facts}\n\n{extra_context}".strip() if facts else extra_context
    if overlay is not None:
        instructions = overlay
    else:
        instructions = persona_overlay(persona)
        if cfg.overlay and "JARVIS_PHASE1_OK" in cfg.overlay:
            instructions = cfg.overlay
        if facts:
            instructions = f"{instructions}\n\n{facts}"

    await bus.publish(
        new_event(
            "brain.status",
            {"state": "thinking", "session_id": session_id, "persona": persona},
            source="brain",
        )
    )
    chunks: list[str] = []
    async for ev in hermes.chat_stream(
        session_id, user_text, instructions=instructions
    ):
        piece = _delta_text(ev.name, ev.data)
        if ev.name == "error":
            raise HermesError(str(ev.data.get("message") or ev.data))
        if piece:
            chunks.append(piece)
            await bus.publish(
                new_event(
                    "assistant.delta",
                    {"text": piece, "session_id": session_id},
                    source="brain",
                )
            )
        elif ev.name in {"assistant.completed", "run.completed", "done"}:
            final = ev.data.get("text") or ev.data.get("output") or ev.data.get(
                "content"
            )
            if isinstance(final, str) and final and not chunks:
                chunks.append(final)
    reply = "".join(chunks).strip()
    await bus.publish(
        new_event(
            "assistant.text",
            {"text": reply, "session_id": session_id},
            source="brain",
        )
    )
    if memory and user_text:
        memory.add(user_text, role="user")
        if reply:
            memory.add(reply, role="assistant")
    if tts and reply:
        await speak_reply(tts, bus, reply, voice=voice, session_id=session_id)
    await bus.publish(
        new_event(
            "brain.status",
            {"state": "idle", "session_id": session_id},
            source="brain",
        )
    )
    await bus.publish(
        new_event(
            "hud.set_mode",
            {"operational": "standby", "visual": persona},
            source="brain",
        )
    )
    return reply


async def speak_reply(
    tts: LocalTTS,
    bus: EventBus,
    text: str,
    *,
    voice: str = "jarvis",
    session_id: str | None = None,
) -> PcmChunk:
    """Synthesize locally and fan out hud.speak + PCM on /ws/voice."""
    events: list[Event] = []
    previous = tts.on_event

    def _capture(event: Event) -> None:
        events.append(event)
        if previous:
            previous(event)

    tts.on_event = _capture
    try:
        chunk = await asyncio.to_thread(tts.speak_text, text, voice=voice)
    finally:
        tts.on_event = previous
    for event in events:
        if session_id is not None:
            event.payload["session_id"] = session_id
        await bus.publish(event)
    if chunk.pcm:
        await bus.send_pcm(chunk.pcm, chunk.sample_rate)
    return chunk


def collect_bus_events(bus: EventBus) -> list[Event]:
    seen: list[Event] = []

    def _keep(event: Event) -> None:
        seen.append(event)

    bus.subscribe(_keep)
    return seen
