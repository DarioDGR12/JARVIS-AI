from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def write_wav(path: str | Path, pcm: bytes, sample_rate: int, *, channels: int = 1) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return dest


def pcm_rms(pcm: bytes) -> float:
    if len(pcm) < 2:
        return 0.0
    n = len(pcm) // 2
    samples = struct.unpack("<" + "h" * n, pcm[: n * 2])
    return math.sqrt(sum(s * s for s in samples) / n)


def wav_info(path: str | Path) -> dict[str, float | int | str]:
    with wave.open(str(path), "rb") as wav:
        rate = wav.getframerate()
        frames = wav.getnframes()
        pcm = wav.readframes(frames)
    return {
        "path": str(path),
        "sample_rate": rate,
        "frames": frames,
        "duration_s": frames / rate if rate else 0.0,
        "rms": pcm_rms(pcm),
        "bytes": len(pcm),
    }
