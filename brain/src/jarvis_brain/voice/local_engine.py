from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

WakeFn = Callable[[bytes, int], bool]
SttFn = Callable[[bytes, int], str]


class LocalVoiceEngine:
    """Optional openWakeWord + faster-whisper. Missing packages → HUD Web Speech."""

    def __init__(
        self,
        *,
        wake: WakeFn | None = None,
        stt: SttFn | None = None,
    ) -> None:
        self._wake_fn = wake
        self._stt_fn = stt
        self.wake_name: str | None = None
        self.stt_name: str | None = None
        self.listening = False
        self._buf = bytearray()
        self._probe()

    def _probe(self) -> None:
        if self._wake_fn is None:
            self._wake_fn, self.wake_name = _load_openwakeword()
        else:
            self.wake_name = "test"
        if self._stt_fn is None:
            self._stt_fn, self.stt_name = _load_faster_whisper()
        else:
            self.stt_name = "test"

    def snapshot(self) -> dict[str, Any]:
        return {
            "wake": self.wake_name,
            "stt": self.stt_name,
            "listening": self.listening,
            "loaded": bool(self._wake_fn or self._stt_fn),
        }

    def ingest_pcm(self, pcm: bytes, sample_rate: int = 16000) -> dict[str, Any] | None:
        if not pcm:
            return None
        if self._wake_fn and not self.listening:
            try:
                if self._wake_fn(pcm, sample_rate):
                    self.listening = True
                    self._buf.clear()
                    return {"kind": "wake", "phrase": "jarvis"}
            except Exception:
                return None
        if self.listening or (self._stt_fn and not self._wake_fn):
            self._buf.extend(pcm)
            # ~1.5 s @ 16 kHz s16le mono
            if len(self._buf) >= sample_rate * 2 * 15 // 10:
                return self.flush(sample_rate)
        return None

    def flush(self, sample_rate: int = 16000) -> dict[str, Any] | None:
        blob = bytes(self._buf)
        self._buf.clear()
        self.listening = False
        if not blob or not self._stt_fn:
            return None
        try:
            text = (self._stt_fn(blob, sample_rate) or "").strip()
        except Exception:
            return None
        if not text:
            return None
        return {"kind": "transcript", "text": text}


def _load_openwakeword() -> tuple[WakeFn | None, str | None]:
    if os.environ.get("JARVIS_WAKE", "1") in {"0", "false", "no"}:
        return None, None
    try:
        import openwakeword  # type: ignore
        from openwakeword.model import Model  # type: ignore
    except Exception:
        return None, None
    try:
        model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    except Exception:
        return None, None

    def _wake(pcm: bytes, sample_rate: int) -> bool:
        import numpy as np  # type: ignore

        audio = np.frombuffer(pcm, dtype=np.int16)
        if sample_rate != 16000 and audio.size:
            # crude decimate / repeat; OWW wants 16 kHz
            ratio = sample_rate / 16000
            idx = (np.arange(int(audio.size / ratio)) * ratio).astype(int)
            audio = audio[idx.clip(0, audio.size - 1)]
        scores = model.predict(audio)
        val = scores.get("hey_jarvis") or scores.get("hey jarvis") or 0
        return float(val) >= float(os.environ.get("JARVIS_WAKE_SCORE", "0.5"))

    _ = openwakeword
    return _wake, "openwakeword"


def _load_faster_whisper() -> tuple[SttFn | None, str | None]:
    if os.environ.get("JARVIS_WHISPER", "1") in {"0", "false", "no"}:
        return None, None
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        return None, None
    name = os.environ.get("JARVIS_WHISPER_MODEL", "tiny")
    try:
        model = WhisperModel(name, device="cpu", compute_type="int8")
    except Exception:
        return None, None

    def _stt(pcm: bytes, sample_rate: int) -> str:
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(pcm)
        buf.seek(0)
        segments, _info = model.transcribe(buf, language="es", beam_size=1)
        return " ".join(seg.text.strip() for seg in segments).strip()

    return _stt, "faster-whisper"
