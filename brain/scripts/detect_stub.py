#!/usr/bin/env python3
"""Protocol stub for JARVIS_YOLO_DETECT. Not ultralytics. Not AGPL.

Real YOLO lives *outside* this repo:

    export JARVIS_YOLO_DETECT=~/.local/share/jarvis/detect.py

JSONL stdin:
    {"type":"tick","camera":"door"}
    {"type":"frame","camera":"door","jpeg_b64":"..."}

JSONL stdout:
    {"type":"detection","kind":"person","camera":"door","score":0.8,"text":"visita"}
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    emit = os.environ.get("JARVIS_STUB_DETECT", "1") not in {"0", "false", "no"}
    for raw in sys.stdin:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        if msg.get("type") not in {"tick", "frame"}:
            continue
        if not emit:
            continue
        sys.stdout.write(
            json.dumps(
                {
                    "type": "detection",
                    "kind": "person",
                    "camera": msg.get("camera") or "door",
                    "score": 0.9,
                    "text": "stub person",
                }
            )
            + "\n"
        )
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
