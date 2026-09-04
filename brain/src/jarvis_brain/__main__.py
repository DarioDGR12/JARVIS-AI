from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import httpx

from jarvis_brain.bus.server import EventBus, serve_bus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import HermesClient, HermesError
from jarvis_brain.turn import run_text_turn, speak_reply
from jarvis_brain.voice.config import VoiceConfig
from jarvis_brain.voice.tts import LocalTTS
from jarvis_brain.voice.wav import wav_info, write_wav

log = logging.getLogger("jarvis")


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


async def _chat(args: argparse.Namespace) -> int:
    cfg = BrainConfig.from_env()
    bus = EventBus()
    hermes = HermesClient(cfg)
    tts = None if args.no_speak else _load_tts(required=bool(args.wav))
    bus_task: asyncio.Task[None] | None = None
    if not args.no_bus:
        bus_task = asyncio.create_task(serve_bus(bus, cfg.bus_host, cfg.bus_port))
        await asyncio.sleep(0.2)
        try:
            async with httpx.AsyncClient() as probe:
                health = await probe.get(
                    f"http://127.0.0.1:{cfg.bus_port}/health", timeout=2.0
                )
            print(f"Bus health {health.status_code} {health.text}", flush=True)
        except Exception as exc:
            print(f"Bus health probe failed: {exc}", flush=True)
    try:
        await hermes.ping()
        session_id = await hermes.ensure_session()
        print(f"Hermes session {session_id} @ {cfg.hermes_base_url}", flush=True)
        print(f"Bus ws://{cfg.bus_host}:{cfg.bus_port}/ws/bus", flush=True)
        print(f"Voice ws://{cfg.bus_host}:{cfg.bus_port}/ws/voice", flush=True)
        print("Overlay (instructions) will be sent every turn.", flush=True)
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
        if bus_task:
            bus_task.cancel()


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
    else:
        print(
            "QA: reply did not contain JARVIS_PHASE1_OK — overlay may not "
            "have reached the model.",
            file=sys.stderr,
        )
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
    cfg = BrainConfig.from_env()
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


async def _serve() -> int:
    cfg = BrainConfig.from_env()
    bus = EventBus()
    await serve_bus(bus, cfg.bus_host, cfg.bus_port)
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="jarvis-brain")
    sub = parser.add_subparsers(dest="cmd", required=True)
    chat = sub.add_parser("chat", help="text turn against Hermes")
    chat.add_argument("-m", "--message", help="single message, then exit")
    chat.add_argument("--once", action="store_true", help="read one stdin line")
    chat.add_argument("--no-bus", action="store_true", help="skip WS server")
    chat.add_argument("--no-speak", action="store_true", help="skip local TTS")
    chat.add_argument("--wav", help="write the spoken reply to a WAV file")
    speak = sub.add_parser("speak", help="local TTS only (no Hermes)")
    speak.add_argument("-m", "--message", help="text to speak")
    speak.add_argument(
        "--wav",
        default="/tmp/jarvis-speak.wav",
        help="output WAV path",
    )
    speak.add_argument("--voice", default="jarvis", choices=("jarvis", "companion"))
    sub.add_parser("serve", help="run the event bus only")
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        return asyncio.run(_serve())
    if args.cmd == "speak":
        return asyncio.run(_speak(args))
    return asyncio.run(_chat(args))


if __name__ == "__main__":
    raise SystemExit(main())
