#!/usr/bin/env python3
"""Write a dark/gold JARVIS mark as PNG + ICO (no extra deps)."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


def _png(width: int, height: int, rgba: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b""
    row = width * 4
    for y in range(height):
        raw += b"\x00" + rgba[y * row : (y + 1) * row]
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(raw, 9)),
            chunk(b"IEND", b""),
        ]
    )


def _mark(size: int) -> bytes:
    px = bytearray(size * size * 4)
    cx = cy = (size - 1) / 2
    r_outer = size * 0.42
    r_inner = size * 0.30
    for y in range(size):
        for x in range(size):
            dx = x - cx
            dy = y - cy
            d = (dx * dx + dy * dy) ** 0.5
            i = (y * size + x) * 4
            if d <= r_outer:
                gold = 0.55 + 0.45 * max(0.0, 1 - d / r_outer)
                px[i] = int(212 * gold)
                px[i + 1] = int(179 * gold)
                px[i + 2] = int(106 * gold)
                px[i + 3] = 255
                # cut a J-shaped gap
                in_stem = abs(dx) < size * 0.08 and -size * 0.18 < dy < size * 0.16
                in_hook = (
                    dy > size * 0.10
                    and d > r_inner * 0.55
                    and dx > -size * 0.16
                    and dx < size * 0.18
                )
                if in_stem or in_hook:
                    px[i] = 7
                    px[i + 1] = 9
                    px[i + 2] = 13
            else:
                px[i] = 7
                px[i + 1] = 9
                px[i + 2] = 13
                px[i + 3] = 255
    return bytes(px)


def _ico(png32: bytes) -> bytes:
    # PNG-compressed ICO (Vista+)
    return b"".join(
        [
            struct.pack("<HHH", 0, 1, 1),
            struct.pack("<BBBBHHII", 32, 32, 0, 0, 1, 32, len(png32), 22),
            png32,
        ]
    )


def main() -> None:
    dest = Path(__file__).resolve().parents[1] / "src-tauri" / "icons"
    dest.mkdir(parents=True, exist_ok=True)
    sizes = {32: "32x32.png", 128: "128x128.png", 256: "256x256.png", 512: "icon.png"}
    pngs: dict[int, bytes] = {}
    for size, name in sizes.items():
        pngs[size] = _png(size, size, _mark(size))
        (dest / name).write_bytes(pngs[size])
    (dest / "henry.png").write_bytes(pngs[512])
    (dest / "icon.ico").write_bytes(_ico(pngs[32]))
    print(f"wrote icons in {dest}")


if __name__ == "__main__":
    main()
