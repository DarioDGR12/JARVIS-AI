from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import httpx

from jarvis_brain.bus.server import EventBus, serve_bus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import HermesClient, HermesError
from jarvis_brain.turn import run_text_turn

log = logging.getLogger("jarvis")


async def _chat(args: argparse.Namespace) -> int:
    cfg = BrainConfig.from_env()
    bus = EventBus()
    hermes = HermesClient(cfg)
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
        print("Overlay (instructions) will be sent every turn.", flush=True)
        if args.message:
            return await _one_turn(args.message, cfg, hermes, bus, session_id)
        if args.once:
            line = sys.stdin.readline()
            if not line.strip():
                print("empty input", file=sys.stderr)
                return 2
            return await _one_turn(line, cfg, hermes, bus, session_id)
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
            rc = await _one_turn(line, cfg, hermes, bus, session_id)
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
    sub.add_parser("serve", help="run the event bus only")
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        return asyncio.run(_serve())
    return asyncio.run(_chat(args))


if __name__ == "__main__":
    raise SystemExit(main())
