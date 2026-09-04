from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GrabResult:
    png: bytes
    backend: str
    width: int
    height: int


class CaptureError(RuntimeError):
    pass


def session_type() -> str:
    env = (os.environ.get("XDG_SESSION_TYPE") or "").lower()
    if env in {"wayland", "x11"}:
        return env
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def _read_png(path: Path) -> bytes:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise CaptureError("not a png")
    return data


def _png_size(png: bytes) -> tuple[int, int]:
    if len(png) < 24:
        return 0, 0
    return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")


def _run(cmd: list[str], timeout: float = 8.0) -> bool:
    try:
        return subprocess.run(cmd, timeout=timeout, capture_output=True).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _grab_ffmpeg(dest: Path) -> bool:
    display = os.environ.get("DISPLAY") or ":0"
    size = os.environ.get("JARVIS_SCREEN_SIZE") or "1280x800"
    return _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "x11grab",
            "-video_size",
            size,
            "-i",
            display,
            "-frames:v",
            "1",
            str(dest),
        ],
        timeout=10,
    )


def _grab_portal(dest: Path) -> bool:
    """Best-effort Screenshot portal. Many sessions need an interactive picker."""
    if not shutil.which("gdbus"):
        return False
    try:
        proc = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.freedesktop.portal.Desktop",
                "--object-path",
                "/org/freedesktop/portal/desktop",
                "--method",
                "org.freedesktop.portal.Screenshot.Screenshot",
                "",
                "{'interactive': <false>}",
            ],
            timeout=6,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    # Portal returns a request path; the file URI is async. Treat as unsupported here.
    return False


def grab_screen() -> GrabResult:
    """Capture one frame. Wayland prefers portal; X11 uses ffmpeg/maim. No PNG left on disk."""
    kind = session_type()
    with tempfile.TemporaryDirectory(prefix="jarvis-vision-") as tmp:
        dest = Path(tmp) / "shot.png"
        backends: list[tuple[str, object]] = []
        if kind == "wayland":
            backends.append(("portal", _grab_portal))
            if shutil.which("grim"):
                backends.append(("grim", lambda p: _run(["grim", str(p)])))
        backends.append(("ffmpeg", _grab_ffmpeg))
        if shutil.which("maim"):
            backends.append(("maim", lambda p: _run(["maim", str(p)])))
        if shutil.which("scrot"):
            backends.append(("scrot", lambda p: _run(["scrot", "-o", str(p)])))
        if shutil.which("import"):
            backends.append(("import", lambda p: _run(["import", "-window", "root", str(p)])))
        last = "none"
        for name, fn in backends:
            last = name
            dest.unlink(missing_ok=True)
            try:
                ok = fn(dest)
            except Exception:
                ok = False
            if ok and dest.is_file() and dest.stat().st_size > 32:
                png = _read_png(dest)
                w, h = _png_size(png)
                return GrabResult(png=png, backend=name, width=w, height=h)
        raise CaptureError(f"screen capture failed ({kind}/{last})")
