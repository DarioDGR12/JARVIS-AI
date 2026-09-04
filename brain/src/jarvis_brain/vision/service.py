from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from jarvis_brain.bus.envelope import Event
from jarvis_brain.vision.capture import CaptureError, GrabResult, grab_screen, session_type
from jarvis_brain.vision.fingerprint import average_hash, downscale, encode_jpeg, hamming
from jarvis_brain.vision.ocr import ocr_image


@dataclass
class ScreenShot:
    text: str
    ocr: str
    fingerprint: str
    backend: str
    width: int
    height: int
    changed: bool
    jpeg: bytes = b""
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    source: str = "screen"

    def summary(self) -> str:
        if self.ocr:
            snippet = self.ocr.replace("\n", " ").strip()[:180]
            return f"Pantalla {self.width}×{self.height}: {snippet}"
        return self.text

    def to_payload(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "ocr": self.ocr,
            "regions": [],
            "timestamp": self.timestamp,
            "source": self.source,
            "image_ref": None,
            "fingerprint": self.fingerprint,
            "backend": self.backend,
            "changed": self.changed,
            "width": self.width,
            "height": self.height,
        }


class VisionService:
    """Screen vision. Webcam is owned by the HUD (one getUserMedia)."""

    def __init__(self, grab: Callable[[], GrabResult] | None = None) -> None:
        self._grab = grab or grab_screen
        self.last_fingerprint: str | None = None
        self.last_shot: ScreenShot | None = None
        self.watch_enabled: bool = False
        self.interval_ms: int = 15000
        self.last_error: str | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "source": "screen",
            "session": session_type(),
            "watch": self.watch_enabled,
            "interval_ms": self.interval_ms,
            "last": None if self.last_shot is None else self.last_shot.to_payload(),
            "error": self.last_error,
        }

    def set_watch(self, enabled: bool, interval_ms: int | None = None) -> None:
        if interval_ms is not None:
            self.interval_ms = max(5000, int(interval_ms))
        self.watch_enabled = bool(enabled)

    def capture_once(self) -> ScreenShot:
        grab = self._grab()
        img = downscale(grab.png)
        fp = average_hash(img)
        changed = self.last_fingerprint is None or hamming(fp, self.last_fingerprint) > 0
        ocr = ""
        if changed:
            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
                img.save(tmp.name)
                ocr = ocr_image(Path(tmp.name))
        text = f"Pantalla {img.size[0]}×{img.size[1]} vía {grab.backend}"
        if not changed:
            text += " (sin cambios)"
        shot = ScreenShot(
            text=text,
            ocr=ocr if changed else (self.last_shot.ocr if self.last_shot else ""),
            fingerprint=fp,
            backend=grab.backend,
            width=img.size[0],
            height=img.size[1],
            changed=changed,
            jpeg=encode_jpeg(img) if changed or self.last_shot is None else (self.last_shot.jpeg if self.last_shot else b""),
        )
        self.last_fingerprint = fp
        self.last_shot = shot
        self.last_error = None
        return shot

    def apply(self, event: Event) -> None:
        payload = event.payload or {}
        if event.type == "vision.watch":
            self.set_watch(bool(payload.get("enabled")), payload.get("interval_ms"))
        elif event.type == "vision.screen_context":
            self.last_error = None
        elif event.type == "vision.error":
            self.last_error = str(payload.get("reason") or "error")


def capture_or_error(vision: VisionService) -> ScreenShot:
    try:
        return vision.capture_once()
    except CaptureError as exc:
        vision.last_error = str(exc)
        raise
