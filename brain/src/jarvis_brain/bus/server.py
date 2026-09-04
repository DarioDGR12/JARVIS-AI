from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from jarvis_brain.bus.envelope import Event

log = logging.getLogger("jarvis.bus")
Handler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    """In-process pub/sub plus WS `/ws/bus` and HTTP `POST /api/bus`."""

    def __init__(self) -> None:
        self._handlers: list[Handler] = []
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    async def publish(self, event: Event) -> Event:
        dead: list[WebSocket] = []
        payload = event.to_dict()
        text = json.dumps(payload, ensure_ascii=False)
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)
        for handler in list(self._handlers):
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        return event

    def app(self) -> FastAPI:
        api = FastAPI(title="JARVIS event bus", version="0.1.0")

        @api.get("/health")
        async def health() -> dict[str, object]:
            return {"ok": True, "clients": len(self._clients)}

        @api.post("/api/bus")
        async def http_publish(body: dict) -> JSONResponse:
            try:
                event = Event.from_dict(body)
            except ValueError as exc:
                return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
            await self.publish(event)
            return JSONResponse(event.to_dict())

        @api.websocket("/ws/bus")
        async def ws_bus(ws: WebSocket) -> None:
            await ws.accept()
            async with self._lock:
                self._clients.add(ws)
            try:
                while True:
                    raw = await ws.receive_text()
                    try:
                        event = Event.from_dict(json.loads(raw))
                    except (ValueError, json.JSONDecodeError) as exc:
                        await ws.send_text(
                            json.dumps({"ok": False, "error": str(exc)})
                        )
                        continue
                    await self.publish(event)
            except WebSocketDisconnect:
                pass
            finally:
                async with self._lock:
                    self._clients.discard(ws)

        return api


async def serve_bus(bus: EventBus, host: str, port: int) -> None:
    import uvicorn

    config = uvicorn.Config(
        bus.app(),
        host=host,
        port=port,
        log_level="info",
        lifespan="off",
    )
    server = uvicorn.Server(config)
    log.info("event bus on ws://%s:%s/ws/bus", host, port)
    await server.serve()
