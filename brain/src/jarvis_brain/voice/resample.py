from __future__ import annotations

import array
import math


def resample_pcm_s16le(data: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Mono little-endian int16. Identity if rates match."""
    if src_rate == dst_rate or not data:
        return data
    if src_rate <= 0 or dst_rate <= 0:
        raise ValueError("sample rates must be positive")
    samples = array.array("h")
    samples.frombytes(data)
    if not samples:
        return data
    ratio = dst_rate / src_rate
    out_len = max(1, int(math.floor(len(samples) * ratio)))
    out = array.array("h")
    last = len(samples) - 1
    for i in range(out_len):
        src_idx = i / ratio
        left = int(math.floor(src_idx))
        frac = src_idx - left
        if left >= last:
            out.append(samples[last])
            continue
        a = samples[left]
        b = samples[left + 1]
        out.append(int(a + (b - a) * frac))
    return out.tobytes()
