from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import httpx
import uvicorn

from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import HermesClient, HermesError
from jarvis_brain.product.app import ProductRuntime, attach_product_routes
from jarvis_brain.product.setup import apply_setup, ensure_product_configured, load_product
from jarvis_brain.product.start import (
    console_already_up,
    desktop_bin,
    ensure_stack,
    hermes_up,
    launch_desktop,
    port_in_use,
)
from jarvis_brain.turn import run_text_turn, speak_reply
from jarvis_brain.voice.config import VoiceConfig
from jarvis_brain.voice.tts import LocalTTS
from jarvis_brain.voice.wav import wav_info, write_wav

log = logging.getLogger("jarvis")


def _apply_saved_product() -> None:
    product = load_product()
    if not product:
        return
    if product.qa:
        os.environ.setdefault("JARVIS_QA", "1")
    os.environ.setdefault("JARVIS_HERMES_URL", product.hermes_url)
    if product.tts:
        os.environ.setdefault("JARVIS_TTS_PROVIDER", product.tts)


def _load_tts(*, required: bool) -> LocalTTS | None:
    try:
        tts = LocalTTS(VoiceConfig.from_env())
    except Exception as exc:
        if required:
            raise
        log.warning("TTS unavailable: %s", exc)
        return None
    engine = tts.engine.name if tts.engine else "none"
    print(f"TTS engine {engine}", flush=True)
    return tts


def _brain_root() -> Path:
    return Path(__file__).resolve().parents[2]


async def _chat(args: argparse.Namespace) -> int:
    ensure_product_configured()
    _apply_saved_product()
    cfg = BrainConfig.from_env()
    bus = EventBus()
    hermes = HermesClient(cfg)
    tts = None if args.no_speak else _load_tts(required=bool(args.wav))
    try:
        ensure_stack(_brain_root(), cfg.hermes_api_key)
    except RuntimeError as exc:
        log.warning("%s", exc)
    server: asyncio.Task[None] | None = None
    try:
        await hermes.ping()
        session_id = await hermes.ensure_session()
        print(f"Hermes session {session_id} @ {cfg.hermes_base_url}", flush=True)
        if not args.no_bus:
            server = asyncio.create_task(_serve_http(cfg, bus, hermes, tts, session_id))
            await asyncio.sleep(0.25)
            try:
                async with httpx.AsyncClient() as probe:
                    health = await probe.get(
                        f"http://127.0.0.1:{cfg.bus_port}/health", timeout=2.0
                    )
                print(f"Bus health {health.status_code} {health.text}", flush=True)
            except Exception as exc:
                print(f"Bus health probe failed: {exc}", flush=True)
        print(f"Brain API http://127.0.0.1:{cfg.bus_port}/ (desktop app)", flush=True)
        if args.message:
            return await _one_turn(
                args.message, cfg, hermes, bus, session_id, tts, args.wav
            )
        if args.once:
            line = sys.stdin.readline()
            if not line.strip():
                print("empty input", file=sys.stderr)
                return 2
            return await _one_turn(line, cfg, hermes, bus, session_id, tts, args.wav)
        print("Type a message. Ctrl-D to quit.", flush=True)
        while True:
            try:
                line = await asyncio.to_thread(sys.stdin.readline)
            except (EOFError, KeyboardInterrupt):
                break
            if line == "":
                break
            if not line.strip():
                continue
            rc = await _one_turn(line, cfg, hermes, bus, session_id, tts, args.wav)
            if rc != 0:
                return rc
        return 0
    except HermesError as exc:
        print(f"Hermes error: {exc}", file=sys.stderr)
        return 1
    finally:
        await hermes.close()
        if server:
            server.cancel()


async def _one_turn(
    line: str,
    cfg: BrainConfig,
    hermes: HermesClient,
    bus: EventBus,
    session_id: str,
    tts: LocalTTS | None,
    wav_path: str | None,
) -> int:
    user = line.strip()
    print(f"you> {user}", flush=True)
    try:
        reply = await run_text_turn(
            user_text=user,
            cfg=cfg,
            hermes=hermes,
            bus=bus,
            session_id=session_id,
            tts=tts,
        )
    except HermesError as exc:
        print(f"Hermes error: {exc}", file=sys.stderr)
        return 1
    print(f"jarvis> {reply}", flush=True)
    if "JARVIS_PHASE1_OK" in reply:
        print("QA: instructions overlay reached the model (JARVIS_PHASE1_OK).", flush=True)
    if wav_path and tts and tts.last_chunk and tts.last_chunk.pcm:
        chunk = tts.last_chunk
        dest = write_wav(wav_path, chunk.pcm, chunk.sample_rate)
        info = wav_info(dest)
        print(
            f"WAV {dest} duration={info['duration_s']:.2f}s rms={info['rms']:.1f}",
            flush=True,
        )
        if float(info["rms"]) < 50:
            print("QA: WAV looks silent.", file=sys.stderr)
            return 1
        print("QA: local TTS wrote audible PCM.", flush=True)
    return 0


async def _speak(args: argparse.Namespace) -> int:
    bus = EventBus()
    tts = _load_tts(required=True)
    assert tts is not None
    text = args.message
    if not text:
        text = sys.stdin.read()
    if not text or not text.strip():
        print("empty input", file=sys.stderr)
        return 2
    chunk = await speak_reply(tts, bus, text.strip(), voice=args.voice)
    dest = write_wav(args.wav, chunk.pcm, chunk.sample_rate)
    info = wav_info(dest)
    print(
        f"jarvis> {text.strip()}\n"
        f"WAV {dest} engine={tts.engine.name if tts.engine else '?'} "
        f"rate={chunk.sample_rate} duration={info['duration_s']:.2f}s "
        f"rms={info['rms']:.1f}",
        flush=True,
    )
    if float(info["rms"]) < 50 or float(info["duration_s"]) < 0.2:
        print("QA: TTS output too short or silent.", file=sys.stderr)
        return 1
    print("QA: local TTS audible.", flush=True)
    return 0


async def _serve_http(
    cfg: BrainConfig,
    bus: EventBus,
    hermes: HermesClient,
    tts: LocalTTS | None,
    session_id: str,
) -> None:
    runtime = ProductRuntime(
        cfg=cfg, bus=bus, hermes=hermes, tts=tts, session_id=session_id
    )
    app = attach_product_routes(bus.app(), runtime)
    config = uvicorn.Config(
        app, host=cfg.bus_host, port=cfg.bus_port, log_level="info", lifespan="off"
    )
    log.info("JARVIS brain API on http://127.0.0.1:%s/", cfg.bus_port)
    await uvicorn.Server(config).serve()


async def _open_desktop(port: int) -> int:
    if desktop_bin() is None:
        print(
            "Desktop app not built yet. The product is the Tauri window, not a browser.\n"
            "Build: cd desktop && npm install && npx tauri build",
            file=sys.stderr,
        )
        return 1
    print(f"Opening JARVIS desktop · brain http://127.0.0.1:{port}/", flush=True)
    proc = launch_desktop(brain_url=f"http://127.0.0.1:{port}")
    return int(proc.wait())


async def _start() -> int:
    os.environ.setdefault("JARVIS_BUS_HOST", "127.0.0.1")
    product, created = ensure_product_configured()
    if created:
        print(
            "No setup yet. Starting in demo (local mock, no cloud key).\n"
            "Your model: open Ajustes in the app, or "
            "jarvis setup --provider openai --api-key \"$OPENAI_API_KEY\"",
            flush=True,
        )
    _apply_saved_product()
    cfg = BrainConfig.from_env()
    if console_already_up(cfg.bus_port):
        return await _open_desktop(cfg.bus_port)
    if port_in_use(cfg.bus_port):
        print(
            f"Port {cfg.bus_port} is already in use by another process.",
            file=sys.stderr,
        )
        return 1
    try:
        ensure_stack(_brain_root(), cfg.hermes_api_key)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    bus = EventBus()
    hermes = HermesClient(cfg)
    tts = _load_tts(required=False)
    server: asyncio.Task[None] | None = None
    try:
        await hermes.ping()
        session_id = await hermes.ensure_session()
        print(
            f"JARVIS · {product.mode} · {product.provider} · {product.model}",
            flush=True,
        )
        server = asyncio.create_task(_serve_http(cfg, bus, hermes, tts, session_id))
        for _ in range(40):
            if console_already_up(cfg.bus_port):
                break
            await asyncio.sleep(0.1)
        return await _open_desktop(cfg.bus_port)
    except HermesError as exc:
        print(f"Hermes error: {exc}", file=sys.stderr)
        return 1
    finally:
        if server:
            server.cancel()
        await hermes.close()


async def _serve_only() -> int:
    os.environ.setdefault("JARVIS_BUS_HOST", "127.0.0.1")
    product, created = ensure_product_configured()
    if created:
        print("No setup yet. Starting in demo.", flush=True)
    _apply_saved_product()
    cfg = BrainConfig.from_env()
    if console_already_up(cfg.bus_port):
        print(f"Brain already running at http://127.0.0.1:{cfg.bus_port}/", flush=True)
        return 0
    if port_in_use(cfg.bus_port):
        print(f"Port {cfg.bus_port} is already in use.", file=sys.stderr)
        return 1
    try:
        ensure_stack(_brain_root(), cfg.hermes_api_key)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    bus = EventBus()
    hermes = HermesClient(cfg)
    tts = _load_tts(required=False)
    try:
        await hermes.ping()
        session_id = await hermes.ensure_session()
        print(
            f"JARVIS API · {product.mode} · {product.provider} · {product.model}",
            flush=True,
        )
        await _serve_http(cfg, bus, hermes, tts, session_id)
    except HermesError as exc:
        print(f"Hermes error: {exc}", file=sys.stderr)
        return 1
    finally:
        await hermes.close()
    return 0


def _cmd_setup(args: argparse.Namespace) -> int:
    provider = "demo" if args.demo else args.provider
    if not provider:
        print("Use --demo or --provider openai|anthropic|openrouter|custom", file=sys.stderr)
        return 2
    key = args.api_key or os.environ.get("JARVIS_API_KEY") or ""
    if provider == "demo" and not key:
        key = "sk-local"
    if provider != "demo" and not key:
        print(
            "BYOK requires --api-key (or JARVIS_API_KEY). "
            "The key is written to ~/.hermes/.env (0600), never to git.",
            file=sys.stderr,
        )
        return 2
    try:
        product = apply_setup(
            provider=provider,
            api_key=key,
            model=args.model,
            base_url=args.base_url,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Configured {product.mode} · {product.provider} · {product.model}", flush=True)
    print("Key stored in ~/.hermes/.env (not in the repo).", flush=True)
    print("Start the product: jarvis start", flush=True)
    return 0


def _cmd_status() -> int:
    cfg = BrainConfig.from_env()
    product = load_product()
    print(f"product: {product.mode if product else 'unset'}"
          f"{' · ' + product.provider + ' · ' + product.model if product else ''}")
    print(f"hermes: {cfg.hermes_base_url} "
          f"{'up' if hermes_up(cfg.hermes_base_url, cfg.hermes_api_key) else 'down'}")
    try:
        tts = LocalTTS(VoiceConfig.from_env())
        print(f"tts: {tts.engine.name if tts.engine else 'none'}")
    except Exception as exc:
        print(f"tts: unavailable ({exc})")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    _apply_saved_product()
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="JARVIS — BYOK personal assistant (local TTS, Hermes engine).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    setup = sub.add_parser("setup", help="configure BYOK or demo mode")
    setup.add_argument("--demo", action="store_true", help="local mock model (no cloud key)")
    setup.add_argument("--provider", choices=("openai", "anthropic", "openrouter", "custom", "demo"))
    setup.add_argument("--api-key", help="provider key; stored in ~/.hermes/.env")
    setup.add_argument("--model", help="model id")
    setup.add_argument("--base-url", help="OpenAI-compatible base URL (custom)")

    sub.add_parser("status", help="show product / Hermes / TTS")
    sub.add_parser("start", help="open the desktop app")

    chat = sub.add_parser("chat", help="text turn in the terminal")
    chat.add_argument("-m", "--message", help="single message, then exit")
    chat.add_argument("--once", action="store_true", help="read one stdin line")
    chat.add_argument("--no-bus", action="store_true", help="skip HTTP/WS server")
    chat.add_argument("--no-speak", action="store_true", help="skip local TTS")
    chat.add_argument("--wav", help="write the spoken reply to a WAV file")

    speak = sub.add_parser("speak", help="local TTS only")
    speak.add_argument("-m", "--message", help="text to speak")
    speak.add_argument("--wav", default="/tmp/jarvis-speak.wav")
    speak.add_argument("--voice", default="jarvis", choices=("jarvis", "companion"))
    sub.add_parser("serve", help="brain API only (no window)")
    sub.add_parser("app", help="same as start")

    args = parser.parse_args(argv)
    if args.cmd == "setup":
        return _cmd_setup(args)
    if args.cmd == "status":
        return _cmd_status()
    if args.cmd in {"start", "app"}:
        return asyncio.run(_start())
    if args.cmd == "serve":
        return asyncio.run(_serve_only())
    if args.cmd == "speak":
        return asyncio.run(_speak(args))
    return asyncio.run(_chat(args))


if __name__ == "__main__":
    raise SystemExit(main())
