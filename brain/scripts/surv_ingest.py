#!/usr/bin/env python3
"""External door detector → JARVIS.

YOLO / DeepCamera stay out of this repo (AGPL). A detector you run yourself
POSTs here:

    POST /api/surveillance/alert
    {"kind":"person","camera":"door","score":0.81,"text":"visita"}

Arming the door is a different call and is Howdy-gated.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest a surveillance alert into JARVIS.")
    parser.add_argument("--brain", default="http://127.0.0.1:8765")
    parser.add_argument("--kind", default="motion")
    parser.add_argument("--camera", default="door")
    parser.add_argument("--score", type=float, default=None)
    parser.add_argument("--text", default="movimiento")
    args = parser.parse_args(argv)
    body = {
        "kind": args.kind,
        "camera": args.camera,
        "text": args.text,
    }
    if args.score is not None:
        body["score"] = args.score
    req = urllib.request.Request(
        args.brain.rstrip("/") + "/api/surveillance/alert",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"ingest failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
