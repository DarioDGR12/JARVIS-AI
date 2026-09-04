from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

HOWDY_EXIT = {
    0: "none",
    10: "no_model",
    11: "timeout",
    12: "abort",
    13: "too_dark",
}

COMPARE_CANDIDATES = (
    "/lib/security/howdy/compare.py",
    "/usr/lib/security/howdy/compare.py",
    "/lib64/security/howdy/compare.py",
    "/usr/lib/howdy/compare.py",
    "/usr/libexec/howdy/compare.py",
)

SENSITIVE = frozenset(
    {
        "ha.command",
        "fs.write",
        "shell",
        "vision.watch",
        "surveillance.arm",
    }
)


@dataclass(frozen=True)
class HowdyResult:
    ok: bool
    howdy_exit: int
    error: str
    user: str
    method: str = "howdy"
    confidence: None = None
    ttl_s: int = 300

    def to_payload(self) -> dict:
        return {
            "ok": self.ok,
            "method": self.method,
            "confidence": self.confidence,
            "user": self.user,
            "error": self.error,
            "ttl_s": self.ttl_s,
            "howdy_exit": self.howdy_exit,
        }


@dataclass(frozen=True)
class HowdyStatus:
    enrolled: bool
    compare_path: str | None
    camera: str
    howdy_version: str | None

    def to_payload(self) -> dict:
        return {
            "enrolled": self.enrolled,
            "compare_path": self.compare_path,
            "camera": self.camera,
            "howdy_version": self.howdy_version,
        }


def find_compare(explicit: str | None = None) -> Path | None:
    env = explicit or os.environ.get("JARVIS_HOWDY_COMPARE")
    if env and Path(env).is_file():
        return Path(env)
    for raw in COMPARE_CANDIDATES:
        path = Path(raw)
        if path.is_file():
            return path
    which = shutil.which("howdy")
    if which:
        sibling = Path(which).resolve().parent / "compare.py"
        if sibling.is_file():
            return sibling
    return None


def classify_camera() -> str:
    by_path = Path("/dev/v4l/by-path")
    if by_path.is_dir():
        names = " ".join(p.name.lower() for p in by_path.iterdir())
        if "ir" in names or "infrared" in names:
            return "ir"
        if list(by_path.iterdir()):
            return "rgb"
    if Path("/dev/video0").exists():
        return "rgb"
    return "missing"


class AuthGate:
    """Howdy compare.py + TTL cache. Sensitive tools fail closed if Howdy is absent."""

    def __init__(
        self,
        *,
        compare: Path | None = None,
        user: str | None = None,
        ttl_s: int = 300,
        timeout_s: float = 12.0,
    ) -> None:
        self.compare = compare if compare is not None else find_compare()
        self.user = user or os.environ.get("JARVIS_AUTH_USER") or os.environ.get("USER") or "dario"
        self.ttl_s = ttl_s
        self.timeout_s = timeout_s
        self._until = 0.0

    def status(self) -> HowdyStatus:
        return HowdyStatus(
            enrolled=self.compare is not None,
            compare_path=str(self.compare) if self.compare else None,
            camera=classify_camera(),
            howdy_version=None,
        )

    def cached(self) -> bool:
        return time.time() < self._until

    def clear(self) -> None:
        self._until = 0.0

    def is_sensitive(self, tool: str) -> bool:
        return tool in SENSITIVE

    def verify(self, *, reason: str, tool: str, force: bool = False) -> HowdyResult:
        if not force and self.cached():
            return HowdyResult(
                ok=True,
                howdy_exit=0,
                error="none",
                user=self.user,
                ttl_s=int(self._until - time.time()),
            )
        if self.compare is None:
            return HowdyResult(
                ok=False,
                howdy_exit=10,
                error="no_model",
                user=self.user,
                ttl_s=0,
            )
        try:
            proc = subprocess.run(
                ["python3", str(self.compare), self.user],
                timeout=self.timeout_s,
                capture_output=True,
                text=True,
            )
            code = int(proc.returncode)
        except subprocess.TimeoutExpired:
            code = 11
        except OSError:
            code = 12
        error = HOWDY_EXIT.get(code, "abort")
        ok = code == 0
        if ok:
            self._until = time.time() + self.ttl_s
        return HowdyResult(
            ok=ok,
            howdy_exit=code,
            error=error if not ok else "none",
            user=self.user,
            ttl_s=self.ttl_s if ok else 0,
        )

    def require(self, tool: str, *, reason: str | None = None) -> HowdyResult:
        if not self.is_sensitive(tool):
            return HowdyResult(
                ok=True, howdy_exit=0, error="none", user=self.user, ttl_s=0
            )
        return self.verify(reason=reason or tool, tool=tool)
