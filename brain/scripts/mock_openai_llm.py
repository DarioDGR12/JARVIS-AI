#!/usr/bin/env python3
"""Tiny OpenAI-compatible chat server for Phase 1 Hermes verification.

If the request system prompt contains JARVIS_PHASE1_OK, the reply includes it.
That is how we prove Hermes forwarded `instructions` to the model.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


MARKER = "JARVIS_PHASE1_OK"
LAST_PATH = Path(os.environ.get("JARVIS_MOCK_LLM_LAST", "/tmp/jarvis-mock-llm-last.json"))
SEEN_OVERLAY = {"yes": False, "system": "", "user": "", "hits": 0, "requests": 0}


def reply_for_messages(messages: list) -> tuple[str, bool, str, str]:
    """Return (reply_text, overlay_hit, system, last_user)."""
    system_bits: list[str] = []
    last_user = ""
    for msg in messages:
        role = (msg or {}).get("role")
        content = (msg or {}).get("content") or ""
        if isinstance(content, list):
            content = " ".join(
                str(p.get("text") or "") for p in content if isinstance(p, dict)
            )
        if role == "system":
            system_bits.append(str(content))
        if role == "user":
            last_user = str(content)
    system = "\n".join(system_bits)
    hit = MARKER in system
    if hit:
        text = f"Acknowledged. {MARKER}. You said: {last_user[:120] or 'nothing'}."
    else:
        text = (
            "Overlay token missing from system prompt. "
            f"You said: {last_user[:120] or 'nothing'}."
        )
    return text, hit, system, last_user


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        print("[mock-llm] " + (fmt % args), flush=True)

    def _json(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/v1/models"):
            self._json(
                200,
                {
                    "object": "list",
                    "data": [{"id": "mock-jarvis", "object": "model"}],
                },
            )
            return
        if self.path.split("?", 1)[0] in {"/health", "/"}:
            self._json(
                200,
                {
                    "ok": True,
                    "overlay_seen": SEEN_OVERLAY["yes"],
                    "hits": SEEN_OVERLAY["hits"],
                    "requests": SEEN_OVERLAY["requests"],
                },
            )
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return
        messages = req.get("messages") or []
        if not messages and isinstance(req.get("input"), list):
            messages = req["input"]
        text, hit, system, last_user = reply_for_messages(messages)
        SEEN_OVERLAY["system"] = system
        SEEN_OVERLAY["user"] = last_user
        SEEN_OVERLAY["yes"] = SEEN_OVERLAY["yes"] or hit
        SEEN_OVERLAY["requests"] += 1
        if hit:
            SEEN_OVERLAY["hits"] += 1
        try:
            LAST_PATH.write_text(
                json.dumps(
                    {
                        "overlay_hit": hit,
                        "user": last_user,
                        "system_len": len(system),
                        "system_has_marker": hit,
                        "path": self.path,
                        "stream": bool(req.get("stream")),
                    },
                    indent=2,
                )
            )
        except OSError:
            pass
        print(f"[mock-llm] overlay_hit={hit} user={last_user!r:.80}", flush=True)
        if req.get("stream"):
            self._stream(text)
            return
        self._json(
            200,
            {
                "id": "chatcmpl-jarvis-phase1",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 8,
                    "total_tokens": 16,
                },
            },
        )

    def _stream(self, text: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        first = {
            "id": "chatcmpl-jarvis-phase1",
            "object": "chat.completion.chunk",
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": text},
                    "finish_reason": None,
                }
            ],
        }
        last = {
            "id": "chatcmpl-jarvis-phase1",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 8,
                "completion_tokens": 8,
                "total_tokens": 16,
            },
        }
        self.wfile.write(f"data: {json.dumps(first)}\n\n".encode())
        self.wfile.write(f"data: {json.dumps(last)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main() -> None:
    host = os.environ.get("JARVIS_MOCK_LLM_HOST", "127.0.0.1")
    port = int(os.environ.get("JARVIS_MOCK_LLM_PORT", "18765"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"mock OpenAI LLM on http://{host}:{port}/v1", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
