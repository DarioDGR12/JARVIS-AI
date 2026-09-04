from __future__ import annotations

import asyncio
import base64
import io
import wave
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import HermesClient, HermesError
from jarvis_brain.product.setup import load_product, public_status
from jarvis_brain.turn import run_text_turn
from jarvis_brain.voice.tts import LocalTTS

CONSOLE = Path(__file__).resolve().parents[1] / "console" / "static" / "index.html"


class ProductRuntime:
    def __init__(
        self,
        *,
        cfg: BrainConfig,
        bus: EventBus,
        hermes: HermesClient,
        tts: LocalTTS | None,
        session_id: str,
    ) -> None:
        self.cfg = cfg
        self.bus = bus
        self.hermes = hermes
        self.tts = tts
        self.session_id = session_id
        self.lock = asyncio.Lock()


def attach_product_routes(app: FastAPI, runtime: ProductRuntime) -> FastAPI:
    @app.get("/")
    async def console() -> FileResponse:
        return FileResponse(CONSOLE, media_type="text/html")

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
            "bus": {
                "clients": len(runtime.bus._clients),
                "voice_clients": len(runtime.bus._voice_clients),
            },
        }

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
