from __future__ import annotations

import asyncio
import base64
import io
import wave
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from jarvis_brain.auth.howdy import AuthGate
from jarvis_brain.bus.envelope import new_event
from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.ha.client import HomeAssistant, load_ha_config, write_ha_config
from jarvis_brain.hermes.client import HermesClient, HermesError
from jarvis_brain.hud.state import HUD_VIEWS, HudState
from jarvis_brain.map.feeds import filter_feeds, query_feeds
from jarvis_brain.map.state import MapState
from jarvis_brain.memory.store import LocalMemory
from jarvis_brain.product.providers import PROVIDERS
from jarvis_brain.product.setup import apply_setup, load_product, public_status
from jarvis_brain.product.start import ensure_stack
from jarvis_brain.tools.stats import system_stats
from jarvis_brain.turn import run_text_turn
from jarvis_brain.vision.service import VisionService
from jarvis_brain.voice.tts import LocalTTS


def _brain_root() -> Path:
    return Path(__file__).resolve().parents[3]


class ProductRuntime:
    def __init__(
        self,
        *,
        cfg: BrainConfig,
        bus: EventBus,
        hermes: HermesClient,
        tts: LocalTTS | None,
        session_id: str,
        brain_root: Path | None = None,
        auth: AuthGate | None = None,
        memory: LocalMemory | None = None,
        ha: HomeAssistant | None = None,
        hud: HudState | None = None,
        world: MapState | None = None,
        vision: VisionService | None = None,
    ) -> None:
        self.cfg = cfg
        self.bus = bus
        self.hermes = hermes
        self.tts = tts
        self.session_id = session_id
        self.brain_root = brain_root or _brain_root()
        self.auth = auth or AuthGate()
        self.memory = memory
        self.ha = ha or HomeAssistant()
        self.hud = hud or HudState()
        self.world = world or MapState()
        self.vision = vision or VisionService()
        self.lock = asyncio.Lock()
        self._watch_task: asyncio.Task[None] | None = None
        self.bus.subscribe(self.hud.apply)
        self.bus.subscribe(self.world.apply)
        self.bus.subscribe(self.vision.apply)

    def ensure_watch_task(self) -> None:
        if self._watch_task is None or self._watch_task.done():
            self._watch_task = asyncio.create_task(self._watch_loop())

    async def _watch_loop(self) -> None:
        while self.vision.watch_enabled:
            await asyncio.sleep(max(5.0, self.vision.interval_ms / 1000))
            if not self.vision.watch_enabled:
                break
            try:
                shot = await asyncio.to_thread(self.vision.capture_once)
            except Exception as exc:
                await self.bus.publish(
                    new_event("vision.error", {"reason": str(exc)}, source="vision")
                )
                continue
            if shot.changed:
                await self.bus.publish(
                    new_event("vision.screen_context", shot.to_payload(), source="vision")
                )
                await self.bus.publish(
                    new_event(
                        "hud.display",
                        {"kind": "toast", "content": shot.summary(), "title": "visión"},
                        source="vision",
                    )
                )


def attach_product_routes(app: FastAPI, runtime: ProductRuntime) -> FastAPI:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost",
            "http://localhost",
            "https://localhost",
        ],
        allow_origin_regex=r"https?://(127\.0\.0\.1|localhost|tauri\.localhost)(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root() -> dict:
        return {"ok": True, "app": "jarvis-brain", "ui": "desktop"}

    @app.get("/api/status")
    async def status() -> dict:
        product = load_product()
        hermes_ok = False
        try:
            await runtime.hermes.ping()
            hermes_ok = True
        except HermesError:
            hermes_ok = False
        return {
            "ok": hermes_ok,
            "product": public_status(product),
            "hermes": runtime.cfg.hermes_base_url,
            "session_id": runtime.session_id,
            "tts": runtime.tts.engine.name if runtime.tts and runtime.tts.engine else None,
            "ui": "desktop",
            "auth": runtime.auth.status().to_payload(),
            "hud": runtime.hud.snapshot(),
            "map": runtime.world.snapshot(),
            "vision": runtime.vision.snapshot(),
            "ha": {"configured": runtime.ha.cfg.configured, "up": False},
            "bus": {
                "clients": len(runtime.bus._clients),
                "voice_clients": len(runtime.bus._voice_clients),
            },
        }

    @app.get("/api/providers")
    async def providers() -> dict:
        return {
            "ok": True,
            "providers": [
                {
                    "id": spec.id,
                    "model": spec.default_model,
                    "base_url": spec.default_base_url,
                    "key_hint": spec.key_hint,
                }
                for spec in PROVIDERS.values()
            ],
        }

    @app.post("/api/setup")
    async def setup(body: dict) -> JSONResponse:
        provider = str((body or {}).get("provider") or "demo")
        key = str((body or {}).get("api_key") or "")
        model = (body or {}).get("model") or None
        base_url = (body or {}).get("base_url") or None
        if provider == "demo" and not key:
            key = "sk-local"
        try:
            product = apply_setup(
                provider=provider,
                api_key=key,
                model=model,
                base_url=base_url,
            )
        except ValueError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
        warning = None
        try:
            ensure_stack(runtime.brain_root, runtime.cfg.hermes_api_key)
            runtime.session_id = await runtime.hermes.ensure_session()
        except Exception as exc:
            warning = str(exc)
        return JSONResponse(
            {
                "ok": True,
                "product": public_status(product),
                "session_id": runtime.session_id,
                "warning": warning,
            }
        )

    @app.post("/api/chat")
    async def chat(body: dict) -> JSONResponse:
        text = str((body or {}).get("message") or "").strip()
        if not text:
            return JSONResponse({"ok": False, "error": "empty message"}, status_code=400)
        async with runtime.lock:
            try:
                reply = await run_text_turn(
                    user_text=text,
                    cfg=runtime.cfg,
                    hermes=runtime.hermes,
                    bus=runtime.bus,
                    session_id=runtime.session_id,
                    tts=runtime.tts,
                    memory=runtime.memory,
                    vision=runtime.vision,
                )
            except HermesError as exc:
                return JSONResponse({"ok": False, "error": str(exc)}, status_code=502)
        audio = None
        if runtime.tts and runtime.tts.last_chunk and runtime.tts.last_chunk.pcm:
            audio = _wav_b64(
                runtime.tts.last_chunk.pcm, runtime.tts.last_chunk.sample_rate
            )
        return JSONResponse(
            {
                "ok": True,
                "reply": reply,
                "session_id": runtime.session_id,
                "audio_wav_b64": audio,
                "tts": runtime.tts.engine.name if runtime.tts and runtime.tts.engine else None,
                "hud": runtime.hud.snapshot(),
                "vision": runtime.vision.snapshot(),
            }
        )

    @app.get("/api/hud")
    async def hud_state() -> dict:
        return {"ok": True, **runtime.hud.snapshot()}

    @app.post("/api/hud/view")
    async def hud_view(body: dict) -> JSONResponse:
        view = str((body or {}).get("view") or "")
        if view not in HUD_VIEWS:
            return JSONResponse({"ok": False, "error": f"unknown view {view}"}, status_code=400)
        await runtime.bus.publish(
            new_event("hud.show_view", {"view": view, "visible": True}, source="hud")
        )
        return JSONResponse({"ok": True, **runtime.hud.snapshot()})

    @app.post("/api/hud/click")
    async def hud_click(body: dict) -> JSONResponse:
        await runtime.bus.publish(
            new_event(
                "hud.click",
                {
                    "target": (body or {}).get("target"),
                    "id": (body or {}).get("id"),
                    "method": (body or {}).get("method") or "pointer",
                },
                source="hud",
            )
        )
        return JSONResponse({"ok": True})

    @app.post("/api/hud/ready")
    async def hud_ready(body: dict) -> dict:
        await runtime.bus.publish(
            new_event(
                "hud.ready",
                {
                    "views": list(HUD_VIEWS),
                    "camera": bool((body or {}).get("camera")),
                    "viewport": (body or {}).get("viewport") or {},
                },
                source="hud",
            )
        )
        return {"ok": True, **runtime.hud.snapshot()}

    @app.post("/api/hud/camera")
    async def hud_camera(body: dict | None = None) -> dict:
        payload = dict(body or {})
        await runtime.bus.publish(new_event("hud.camera", payload, source="hud"))
        return {"ok": True, **runtime.hud.snapshot()}

    @app.get("/api/map")
    async def map_state() -> dict:
        return {"ok": True, **runtime.world.snapshot(), "feeds": runtime.world.visible}

    @app.post("/api/map/focus")
    async def map_focus(body: dict) -> JSONResponse:
        lat = (body or {}).get("lat")
        lon = (body or {}).get("lon")
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            return JSONResponse({"ok": False, "error": "lat and lon required"}, status_code=400)
        await runtime.bus.publish(
            new_event(
                "hud.show_view",
                {"view": "map", "visible": True},
                source="brain",
            )
        )
        await runtime.bus.publish(
            new_event(
                "map.focus",
                {"lat": lat_f, "lon": lon_f, "zoom": (body or {}).get("zoom")},
                source="brain",
            )
        )
        return JSONResponse({"ok": True, **runtime.world.snapshot()})

    @app.post("/api/map/query")
    async def map_query(body: dict) -> JSONResponse:
        q = str((body or {}).get("q") or "")
        hits = query_feeds(runtime.world.feeds, q)
        await runtime.bus.publish(
            new_event("hud.show_view", {"view": "map", "visible": True}, source="brain")
        )
        await runtime.bus.publish(new_event("map.query", {"q": q}, source="brain"))
        return JSONResponse({"ok": True, "hits": hits, **runtime.world.snapshot()})

    @app.post("/api/map/feeds")
    async def map_feeds(body: dict) -> JSONResponse:
        region = (body or {}).get("region")
        tags = (body or {}).get("tags") or []
        hits = filter_feeds(runtime.world.feeds, region=region, tags=tags)
        await runtime.bus.publish(
            new_event("hud.show_view", {"view": "map", "visible": True}, source="brain")
        )
        await runtime.bus.publish(
            new_event("map.show_feeds", {"region": region, "tags": tags}, source="brain")
        )
        return JSONResponse({"ok": True, "feeds": hits, **runtime.world.snapshot()})

    @app.get("/api/vision")
    async def vision_state() -> dict:
        preview = None
        if runtime.vision.last_shot and runtime.vision.last_shot.jpeg:
            preview = base64.b64encode(runtime.vision.last_shot.jpeg).decode("ascii")
        return {"ok": True, **runtime.vision.snapshot(), "preview_jpeg_b64": preview}

    @app.post("/api/vision/capture")
    async def vision_capture(body: dict | None = None) -> JSONResponse:
        await runtime.bus.publish(
            new_event("vision.capture", {"mode": (body or {}).get("mode") or "once"}, source="hud")
        )
        try:
            shot = await asyncio.to_thread(runtime.vision.capture_once)
        except Exception as exc:
            await runtime.bus.publish(
                new_event("vision.error", {"reason": str(exc)}, source="vision")
            )
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=502)
        await runtime.bus.publish(
            new_event("vision.screen_context", shot.to_payload(), source="vision")
        )
        await runtime.bus.publish(
            new_event("hud.show_view", {"view": "vision", "visible": True}, source="brain")
        )
        return JSONResponse(
            {
                "ok": True,
                **shot.to_payload(),
                "preview_jpeg_b64": base64.b64encode(shot.jpeg).decode("ascii") if shot.jpeg else None,
            }
        )

    @app.post("/api/vision/watch")
    async def vision_watch(body: dict) -> JSONResponse:
        enabled = bool((body or {}).get("enabled"))
        interval = (body or {}).get("interval_ms")
        if enabled:
            gate = runtime.auth.require("vision.watch", reason="vision.watch")
            if not gate.ok:
                await runtime.bus.publish(
                    new_event("auth.challenge", {"reason": "vision.watch", "tool": "vision.watch"}, source="brain")
                )
                await runtime.bus.publish(
                    new_event(
                        "hud.camera",
                        {"hold": True, "reason": "vision.watch"},
                        source="brain",
                    )
                )
                await runtime.bus.publish(
                    new_event("auth.result", gate.to_payload(), source="auth")
                )
                await runtime.bus.publish(
                    new_event("hud.camera", {"hold": False, "reason": "vision.watch"}, source="auth")
                )
                return JSONResponse(
                    {"ok": False, "error": "auth required", "auth": gate.to_payload()},
                    status_code=403,
                )
        await runtime.bus.publish(
            new_event(
                "vision.watch",
                {"enabled": enabled, "interval_ms": interval},
                source="hud",
            )
        )
        if enabled:
            runtime.ensure_watch_task()
        return JSONResponse({"ok": True, **runtime.vision.snapshot()})

    @app.get("/api/system")
    async def system() -> dict:
        return {"ok": True, "stats": system_stats(), "auth": runtime.auth.status().to_payload()}

    @app.get("/api/auth")
    async def auth_status() -> dict:
        return {"ok": True, **runtime.auth.status().to_payload(), "cached": runtime.auth.cached()}

    @app.post("/api/auth/challenge")
    async def auth_challenge(body: dict) -> JSONResponse:
        tool = str((body or {}).get("tool") or "shell")
        reason = str((body or {}).get("reason") or tool)
        await runtime.bus.publish(
            new_event(
                "auth.challenge",
                {"reason": reason, "tool": tool, "ttl_s": runtime.auth.ttl_s},
                source="brain",
            )
        )
        await runtime.bus.publish(
            new_event("hud.camera", {"hold": True, "reason": reason}, source="brain")
        )
        result = runtime.auth.verify(reason=reason, tool=tool, force=True)
        await runtime.bus.publish(
            new_event("auth.result", result.to_payload(), source="auth")
        )
        await runtime.bus.publish(
            new_event("hud.camera", {"hold": False, "reason": reason}, source="auth")
        )
        return JSONResponse({"ok": result.ok, **result.to_payload()})

    @app.get("/api/ha/states")
    async def ha_states() -> JSONResponse:
        if not runtime.ha.cfg.configured:
            return JSONResponse(
                {"ok": False, "error": "HA not configured", "states": []},
                status_code=200,
            )
        try:
            states = runtime.ha.states()
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc), "states": []}, status_code=502)
        slim = [
            {
                "entity_id": s.get("entity_id"),
                "state": s.get("state"),
                "name": (s.get("attributes") or {}).get("friendly_name"),
            }
            for s in states
            if str(s.get("entity_id") or "").split(".", 1)[0]
            in {"light", "switch", "binary_sensor", "sensor", "lock", "climate"}
        ]
        return JSONResponse({"ok": True, "states": slim[:80]})

    @app.post("/api/ha/call")
    async def ha_call(body: dict) -> JSONResponse:
        domain = str((body or {}).get("domain") or "")
        service = str((body or {}).get("service") or "")
        entity_id = (body or {}).get("entity_id") or None
        if not domain or not service:
            return JSONResponse({"ok": False, "error": "domain and service required"}, status_code=400)
        gate = runtime.auth.require("ha.command", reason="ha.command")
        if not gate.ok:
            return JSONResponse(
                {"ok": False, "error": "auth required", "auth": gate.to_payload()},
                status_code=403,
            )
        try:
            result = runtime.ha.call(domain, service, entity_id=entity_id)
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=502)
        return JSONResponse({"ok": True, **result})

    @app.post("/api/ha/setup")
    async def ha_setup(body: dict) -> JSONResponse:
        url = str((body or {}).get("url") or "")
        token = str((body or {}).get("token") or "")
        if not url or not token:
            return JSONResponse({"ok": False, "error": "url and token required"}, status_code=400)
        write_ha_config(url, token)
        runtime.ha = HomeAssistant(load_ha_config())
        return JSONResponse({"ok": True, "configured": runtime.ha.cfg.configured})

    @app.get("/api/memory")
    async def memory_search(q: str = "", k: int = 5) -> dict:
        if runtime.memory is None:
            return {"ok": True, "items": []}
        return {"ok": True, "items": runtime.memory.search(q, k=k)}

    @app.post("/api/memory/forget")
    async def memory_forget(body: dict) -> dict:
        if runtime.memory is None:
            return {"ok": True, "removed": 0}
        removed = runtime.memory.forget(
            query=(body or {}).get("query"),
            id=(body or {}).get("id"),
        )
        return {"ok": True, "removed": removed}

    return app


def _wav_b64(pcm: bytes, sample_rate: int) -> str:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return base64.b64encode(buf.getvalue()).decode("ascii")
