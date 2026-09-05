from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from jarvis_brain.ha.client import HAConfig

log = logging.getLogger(__name__)

EventHook = Callable[[dict[str, Any]], Awaitable[None]]


def ws_url(http_url: str) -> str:
    base = (http_url or "").rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :] + "/api/websocket"
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :] + "/api/websocket"
    if base.startswith("ws://") or base.startswith("wss://"):
        return base + ("/api/websocket" if not base.endswith("/api/websocket") else "")
    return ""


class HAWebsocket:
    """Home Assistant /api/websocket. Subscribe only. Never POST /api/states."""

    def __init__(self, cfg: HAConfig | None = None) -> None:
        self.cfg = cfg
        self.connected = False
        self.last_event: dict[str, Any] | None = None
        self.error: str | None = None
        self._msg_id = 1
        self._stop = asyncio.Event()

    def bind(self, cfg: HAConfig | None) -> None:
        self.cfg = cfg
        self.connected = False
        self.error = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "configured": bool(self.cfg and self.cfg.configured),
            "connected": self.connected,
            "url": ws_url(self.cfg.url) if self.cfg else "",
            "last_event": self.last_event,
            "error": self.error,
        }

    def stop(self) -> None:
        self._stop.set()

    async def run(self, on_event: EventHook | None = None) -> None:
        self._stop = asyncio.Event()
        while not self._stop.is_set():
            if not self.cfg or not self.cfg.configured:
                self.connected = False
                self.error = "not-configured"
                await self._stop.wait()
                return
            try:
                await self._session(on_event)
            except asyncio.CancelledError:
                self.connected = False
                raise
            except Exception as exc:
                self.connected = False
                self.error = str(exc)
                log.debug("HA websocket: %s", exc)
            if self._stop.is_set():
                break
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=4.0)
            except asyncio.TimeoutError:
                continue

    async def _session(self, on_event: EventHook | None) -> None:
        import websockets

        url = ws_url(self.cfg.url if self.cfg else "")
        if not url:
            raise RuntimeError("HA websocket URL empty")
        async with websockets.connect(url, open_timeout=6, close_timeout=2) as sock:
            hello = json.loads(await asyncio.wait_for(sock.recv(), timeout=6))
            if hello.get("type") != "auth_required":
                raise RuntimeError(f"unexpected HA hello {hello.get('type')}")
            await sock.send(
                json.dumps({"type": "auth", "access_token": self.cfg.token})
            )
            auth = json.loads(await asyncio.wait_for(sock.recv(), timeout=6))
            if auth.get("type") != "auth_ok":
                raise RuntimeError(auth.get("message") or "HA auth failed")
            self._msg_id += 1
            await sock.send(
                json.dumps(
                    {
                        "id": self._msg_id,
                        "type": "subscribe_events",
                        "event_type": "state_changed",
                    }
                )
            )
            self.connected = True
            self.error = None
            while not self._stop.is_set():
                raw = await asyncio.wait_for(sock.recv(), timeout=30)
                msg = json.loads(raw)
                if msg.get("type") != "event":
                    continue
                event = msg.get("event") or {}
                data = event.get("data") or {}
                payload = {
                    "entity_id": data.get("entity_id"),
                    "new_state": (data.get("new_state") or {}).get("state"),
                    "old_state": (data.get("old_state") or {}).get("state"),
                    "event_type": event.get("event_type") or "state_changed",
                }
                self.last_event = payload
                if on_event is not None:
                    await on_event(payload)
