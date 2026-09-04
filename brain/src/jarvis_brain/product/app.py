from __future__ import annotations

import asyncio
import base64
import io
import wave
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import HermesClient, HermesError
from jarvis_brain.product.providers import PROVIDERS
from jarvis_brain.product.setup import apply_setup, load_product, public_status
from jarvis_brain.product.start import ensure_stack
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
    ) -> None:
        self.cfg = cfg
        self.bus = bus
        self.hermes = hermes
        self.tts = tts
        self.session_id = session_id
        self.brain_root = brain_root or _brain_root()
        self.lock = asyncio.Lock()


def attach_product_routes(app: FastAPI, runtime: ProductRuntime) -> FastAPI:
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

    return app


def _wav_b64(pcm: bytes, sample_rate: int) -> str:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return base64.b64encode(buf.getvalue()).decode("ascii")
