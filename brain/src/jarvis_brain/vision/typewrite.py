from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from jarvis_brain.vision.click import click_region


def type_enabled() -> bool:
    for name in ("JARVIS_VISION_TYPE", "JARVIS_VISION_CLICK"):
        if os.environ.get(name) in {"1", "true", "yes"}:
            return True
    return False


def type_text(text: str, region: dict[str, Any] | None = None) -> dict[str, Any]:
    """Optional wtype / xdotool / ydotool. Default is record-only."""
    payload = {"typed": False, "text": text, "region": region, "reason": "record-only"}
    if not text:
        payload["reason"] = "empty"
        return payload
    if not type_enabled():
        return payload
    if region:
        click_region(region)
    cmd: list[str] | None = None
    tool = None
    if shutil.which("wtype"):
        tool = "wtype"
        cmd = ["wtype", "--", text]
    elif shutil.which("xdotool"):
        tool = "xdotool"
        cmd = ["xdotool", "type", "--", text]
    elif shutil.which("ydotool"):
        tool = "ydotool"
        cmd = ["ydotool", "type", text]
    if not cmd:
        payload["reason"] = "no type tool"
        return payload
    try:
        ok = subprocess.run(cmd, timeout=3, capture_output=True).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    payload["typed"] = ok
    payload["reason"] = tool if ok else f"{tool}-fail"
    return payload
