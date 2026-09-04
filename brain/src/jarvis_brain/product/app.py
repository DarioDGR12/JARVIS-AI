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
from jarvis_brain.memory.store import LocalMemory
from jarvis_brain.product.providers import PROVIDERS
from jarvis_brain.product.setup import apply_setup, load_product, public_status
from jarvis_brain.product.start import ensure_stack
from jarvis_brain.tools.stats import system_stats
from jarvis_brain.turn import run_text_turn
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
        self.lock = asyncio.Lock()


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
            }
        )

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
        result = runtime.auth.verify(reason=reason, tool=tool, force=True)
        await runtime.bus.publish(
            new_event("auth.result", result.to_payload(), source="auth")
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
