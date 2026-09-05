from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, IO


def detector_path() -> Path | None:
    """Out-of-tree YOLO (or a protocol stub). Never import ultralytics here."""
    raw = os.environ.get("JARVIS_YOLO_DETECT")
    candidates = [
        Path(raw) if raw else None,
        Path.home() / ".local/share/jarvis/detect.py",
        Path("/opt/jarvis-yolo/detect.py"),
    ]
    for path in candidates:
        if path is not None and path.is_file():
            return path
    return None


class DetectorChild:
    """JSONL stdin/stdout. AGPL YOLO stays outside this repo."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else detector_path()
        self.proc: subprocess.Popen[str] | None = None
        self.last_error: str | None = None
        self._last_emit = 0.0
        self.debounce_s = float(os.environ.get("JARVIS_YOLO_DEBOUNCE", "8"))

    def snapshot(self) -> dict[str, Any]:
        running = self.proc is not None and self.proc.poll() is None
        return {
            "path": str(self.path) if self.path else None,
            "running": running,
            "error": self.last_error,
            "policy": "yolo-out-of-tree",
        }

    def start(self) -> bool:
        if self.proc is not None and self.proc.poll() is None:
            return True
        if self.path is None:
            self.last_error = "no detector (set JARVIS_YOLO_DETECT)"
            return False
        try:
            self.proc = subprocess.Popen(
                [sys.executable, str(self.path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            self.last_error = None
            return True
        except OSError as exc:
            self.last_error = str(exc)
            self.proc = None
            return False

    def stop(self) -> None:
        if self.proc is None:
            return
        try:
            self.proc.terminate()
            self.proc.wait(timeout=2)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        self.proc = None

    def tick(self, *, camera: str = "door") -> list[dict[str, Any]]:
        if self.proc is None or self.proc.stdin is None or self.proc.stdout is None:
            return []
        line = json.dumps({"type": "tick", "camera": camera, "timestamp": int(time.time() * 1000)})
        try:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
        except OSError as exc:
            self.last_error = str(exc)
            return []
        return self._drain(self.proc.stdout)

    def _drain(self, stdout: IO[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        while True:
            raw = ""
            try:
                import select

                ready, _, _ = select.select([stdout], [], [], 0.05)
                if not ready:
                    break
                raw = stdout.readline()
            except Exception:
                break
            if not raw:
                break
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if str(data.get("type") or "") not in {"detection", "alert"}:
                continue
            now = time.time()
            if now - self._last_emit < self.debounce_s:
                continue
            self._last_emit = now
            out.append(
                {
                    "kind": str(data.get("kind") or "person"),
                    "camera": str(data.get("camera") or "door"),
                    "score": data.get("score"),
                    "text": str(data.get("text") or data.get("kind") or "detección"),
                }
            )
        return out
