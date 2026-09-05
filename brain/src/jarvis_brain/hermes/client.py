from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from jarvis_brain.config import BrainConfig


class HermesError(RuntimeError):
    pass


@dataclass(frozen=True)
class StreamEvent:
    name: str
    data: dict


class HermesClient:
    """Sessions API client. Always sends `instructions` on chat/stream."""

    def __init__(self, cfg: BrainConfig, client: httpx.AsyncClient | None = None) -> None:
        self.cfg = cfg
        self._owned = client is None
        self._http = client or httpx.AsyncClient(timeout=httpx.Timeout(cfg.hermes_timeout_s))

    def _headers(self, *, sse: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.cfg.hermes_api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if sse else "application/json",
            "X-Hermes-Session-Key": self.cfg.hermes_session_key,
        }
        return headers

    async def close(self) -> None:
        if self._owned:
            await self._http.aclose()

    async def ping(self) -> dict:
        r = await self._http.get(
            f"{self.cfg.hermes_base_url}/health",
            headers=self._headers(),
        )
        if r.status_code >= 400:
            r = await self._http.get(
                f"{self.cfg.hermes_base_url}/v1/models",
                headers=self._headers(),
            )
        if r.status_code >= 400:
            raise HermesError(f"Hermes not reachable ({r.status_code}): {r.text[:200]}")
        try:
            return r.json()
        except Exception:
            return {"ok": True, "status": r.status_code}

    async def ensure_session(self, title: str | None = None) -> str:
        title = title or self.cfg.hermes_session_name
        existing = await self._find_session(title)
        if existing:
            return existing
        r = await self._http.post(
            f"{self.cfg.hermes_base_url}/api/sessions",
            headers=self._headers(),
            json={"title": title, "source": "api_server"},
        )
        if r.status_code == 400 and "already in use" in r.text:
            existing = await self._find_session(title)
            if existing:
                return existing
        if r.status_code >= 400:
            raise HermesError(f"create session HTTP {r.status_code}: {r.text[:300]}")
        body = r.json()
        sid = (body.get("session") or body).get("id")
        if not sid:
            raise HermesError(f"session create missing id: {body!r}")
        return str(sid)

    async def _find_session(self, title: str) -> str | None:
        r = await self._http.get(
            f"{self.cfg.hermes_base_url}/api/sessions",
            headers=self._headers(),
            params={"title": title, "limit": 20},
        )
        if r.status_code >= 400:
            return None
        try:
            body = r.json()
        except Exception:
            return None
        for row in body.get("data") or []:
            if str(row.get("title") or "") == title and row.get("id"):
                return str(row["id"])
        return None

    async def chat_stream(
        self,
        session_id: str,
        user_text: str,
        *,
        instructions: str,
    ) -> AsyncIterator[StreamEvent]:
        """POST /api/sessions/{id}/chat/stream with instructions overlay."""
        url = f"{self.cfg.hermes_base_url}/api/sessions/{session_id}/chat/stream"
        # Hermes accepts `message` or `input`; `instructions` becomes ephemeral_system_prompt.
        payload = {
            "message": user_text,
            "input": user_text,
            "instructions": instructions,
        }
        async with self._http.stream(
            "POST",
            url,
            headers=self._headers(sse=True),
            json=payload,
        ) as resp:
            if resp.status_code >= 400:
                text = (await resp.aread()).decode("utf-8", errors="replace")
                raise HermesError(f"chat/stream HTTP {resp.status_code}: {text[:400]}")
            async for event in _parse_sse(resp):
                yield event


async def _parse_sse(resp: httpx.Response) -> AsyncIterator[StreamEvent]:
    name = ""
    async for raw in resp.aiter_lines():
        if not raw:
            continue
        if raw.startswith("event:"):
            name = raw.split(":", 1)[1].strip()
            continue
        if raw.startswith(":"):
            continue
        if not raw.startswith("data:"):
            continue
        blob = raw.split(":", 1)[1].strip()
        if blob in {"", "[DONE]"}:
            continue
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            data = {"text": blob}
        if not isinstance(data, dict):
            data = {"value": data}
        yield StreamEvent(name=name or str(data.get("type") or "message"), data=data)
        name = ""
