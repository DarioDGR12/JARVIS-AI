#!/usr/bin/env python3
"""Out-of-tree YOLO template. Copy this *outside* the repo.

    cp brain/scripts/detect_template.py ~/.local/share/jarvis/detect.py
    export JARVIS_YOLO_DETECT=~/.local/share/jarvis/detect.py

Do NOT import ultralytics in JARVIS-AI. Wire YOLO26n in the copy only.
Protocol: docs/DETECT.md
"""

from __future__ import annotations

import json
import sys


def detect(msg: dict) -> dict | None:
    """Replace this body in the out-of-tree copy. Return None to stay quiet."""
    camera = msg.get("camera") or "door"
    return {
        "type": "detection",
        "kind": "person",
        "camera": camera,
        "score": 0.5,
        "text": "template (wire YOLO outside the repo)",
    }


def main() -> int:
    for raw in sys.stdin:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict) or msg.get("type") not in {"tick", "frame"}:
            continue
        hit = detect(msg)
        if not hit:
            continue
        sys.stdout.write(json.dumps(hit) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
