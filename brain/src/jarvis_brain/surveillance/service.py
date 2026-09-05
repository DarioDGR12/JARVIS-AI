from __future__ import annotations

import time
from typing import Any

from jarvis_brain.bus.envelope import Event


class SurveillanceService:
    """Door agent. YOLO stays out of tree (AGPL). We only ingest alerts."""

    def __init__(self) -> None:
        self.armed: bool = False
        self.last_alert: dict[str, Any] | None = None
        self.last_error: str | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "armed": self.armed,
            "detector": "external",
            "policy": "yolo-out-of-tree",
            "last": self.last_alert,
            "error": self.last_error,
        }

    def set_armed(self, armed: bool) -> None:
        self.armed = bool(armed)
        self.last_error = None

    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        alert = {
            "kind": str(payload.get("kind") or "motion"),
            "camera": str(payload.get("camera") or "door"),
            "score": payload.get("score"),
            "text": str(payload.get("text") or "movimiento"),
            "timestamp": int(payload.get("timestamp") or time.time() * 1000),
            "source": "surveillance",
        }
        self.last_alert = alert
        self.last_error = None
        return alert

    def apply(self, event: Event) -> None:
        payload = event.payload or {}
        if event.type == "surveillance.arm":
            self.set_armed(bool(payload.get("armed") or payload.get("enabled")))
        elif event.type == "surveillance.alert":
            self.ingest(payload)
        elif event.type == "surveillance.error":
            self.last_error = str(payload.get("reason") or "error")
