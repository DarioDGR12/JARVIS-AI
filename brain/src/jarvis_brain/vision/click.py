from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any


def click_region(region: dict[str, Any], *, screen: tuple[int, int] | None = None) -> dict[str, Any]:
    """Optional xdotool. Default is record-only so we don't inject clicks blindly."""
    if os.environ.get("JARVIS_VISION_CLICK") not in {"1", "true", "yes"}:
        return {"clicked": False, "reason": "record-only", "region": region}
    if not shutil.which("xdotool"):
        return {"clicked": False, "reason": "no xdotool", "region": region}
    sw, sh = screen or (1920, 1080)
    x = int((float(region.get("x") or 0) + float(region.get("w") or 0) / 2) * sw)
    y = int((float(region.get("y") or 0) + float(region.get("h") or 0) / 2) * sh)
    try:
        ok = subprocess.run(
            ["xdotool", "mousemove", str(x), str(y), "click", "1"],
            timeout=2,
            capture_output=True,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    return {"clicked": ok, "reason": "xdotool" if ok else "xdotool-fail", "region": region, "x": x, "y": y}
