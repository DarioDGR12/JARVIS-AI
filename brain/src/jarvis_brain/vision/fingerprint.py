from __future__ import annotations

import hashlib
from io import BytesIO

from PIL import Image


MAX_EDGE = 1280


def downscale(png: bytes, max_edge: int = MAX_EDGE) -> Image.Image:
    img = Image.open(BytesIO(png)).convert("RGB")
    w, h = img.size
    edge = max(w, h)
    if edge > max_edge:
        scale = max_edge / edge
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.BILINEAR)
    return img


def average_hash(img: Image.Image) -> str:
    """Perceptual hash: 16×16 quantized RGB. Solid-color frames still differ by hue."""
    small = img.convert("RGB").resize((16, 16), Image.Resampling.BILINEAR)
    quant = small.point(lambda p: (p // 16) * 16)
    return hashlib.sha256(quant.tobytes()).hexdigest()[:16]


def hamming(a: str, b: str) -> int:
    if not a or not b or len(a) != len(b):
        return 16
    return sum(x != y for x, y in zip(a, b))


def encode_jpeg(img: Image.Image, quality: int = 70) -> bytes:
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()
