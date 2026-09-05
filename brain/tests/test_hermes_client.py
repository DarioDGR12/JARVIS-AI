import json

import httpx
import pytest

from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import HermesClient, HermesError


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


@pytest.mark.asyncio
async def test_chat_stream_sends_instructions() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        captured["auth"] = request.headers.get("authorization")
        body = (
            _sse("run.started", {"run_id": "r1"})
            + _sse("assistant.delta", {"delta": "Hello "})
            + _sse("assistant.delta", {"delta": "world"})
            + _sse("run.completed", {"ok": True})
        )
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        cfg = BrainConfig(hermes_base_url="http://hermes.test", hermes_api_key="k")
        client = HermesClient(cfg, client=http)
        events = [
            ev
            async for ev in client.chat_stream(
                "sid-1", "ping", instructions="BE JARVIS JARVIS_PHASE1_OK"
            )
        ]
    assert captured["url"].endswith("/api/sessions/sid-1/chat/stream")
    assert captured["body"]["input"] == "ping"
    assert captured["body"]["message"] == "ping"
    assert captured["body"]["instructions"] == "BE JARVIS JARVIS_PHASE1_OK"
    assert captured["auth"] == "Bearer k"
    deltas = [e.data.get("delta") for e in events if e.name == "assistant.delta"]
    assert deltas == ["Hello ", "world"]


@pytest.mark.asyncio
async def test_ensure_session_reuses_title() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "data": [{"id": "api_existing", "title": "jarvis-main"}],
                },
            )
        return httpx.Response(500, text="should not create")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = HermesClient(BrainConfig(), client=http)
        sid = await client.ensure_session("jarvis-main")
    assert sid == "api_existing"
    assert calls == ["GET /api/sessions"]


@pytest.mark.asyncio
async def test_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = HermesClient(BrainConfig(), client=http)
        with pytest.raises(HermesError):
            await client.ensure_session()
