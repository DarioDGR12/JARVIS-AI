from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from jarvis_brain.vision.ocr import ocr_image

_TOKEN = re.compile(r"https?://\S+|[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]{3,}")


def ocr_tsv_regions(path: Path, *, width: int, height: int) -> list[dict[str, Any]]:
    bin_path = shutil.which("tesseract")
    if not bin_path:
        return []
    try:
        proc = subprocess.run(
            [bin_path, str(path), "stdout", "-l", "spa+eng", "--psm", "6", "tsv"],
            capture_output=True,
            timeout=8,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    regions: list[dict[str, Any]] = []
    for line in (proc.stdout or "").splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) < 12:
            continue
        text = cols[11].strip()
        if not text or text == "-":
            continue
        try:
            left, top, w, h = (int(cols[6]), int(cols[7]), int(cols[8]), int(cols[9]))
        except ValueError:
            continue
        if w <= 0 or h <= 0:
            continue
        regions.append(
            {
                "id": f"r{len(regions)+1}",
                "text": text[:80],
                "x": round(left / max(width, 1), 4),
                "y": round(top / max(height, 1), 4),
                "w": round(w / max(width, 1), 4),
                "h": round(h / max(height, 1), 4),
            }
        )
        if len(regions) >= 12:
            break
    return regions


def regions_from_text(ocr: str, *, width: int = 1, height: int = 1) -> list[dict[str, Any]]:
    tokens = [m.group(0) for m in _TOKEN.finditer(ocr or "")][:8]
    if not tokens:
        return []
    step = 1.0 / max(len(tokens), 1)
    out: list[dict[str, Any]] = []
    for i, token in enumerate(tokens):
        out.append(
            {
                "id": f"t{i+1}",
                "text": token[:80],
                "x": 0.08,
                "y": round(0.08 + i * step * 0.8, 4),
                "w": 0.84,
                "h": round(min(0.12, step * 0.7), 4),
            }
        )
    return out


def collect_regions(path: Path | None, ocr: str, *, width: int, height: int) -> list[dict[str, Any]]:
    if path is not None:
        boxed = ocr_tsv_regions(path, width=width, height=height)
        if boxed:
            return boxed
    return regions_from_text(ocr, width=width, height=height)


def match_region(regions: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    needle = (query or "").strip().lower()
    if not needle:
        return regions[0] if regions else None
    for region in regions:
        if needle in str(region.get("text") or "").lower():
            return region
    return None


def ocr_with_regions(path: Path) -> tuple[str, list[dict[str, Any]]]:
    text = ocr_image(path)
    try:
        from PIL import Image

        with Image.open(path) as img:
            width, height = img.size
    except Exception:
        width, height = 1, 1
    return text, collect_regions(path, text, width=width, height=height)
