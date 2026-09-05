from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

from jarvis_brain.bus.envelope import Event
from jarvis_brain.voice.clean import clean_for_tts, split_sentences
from jarvis_brain.voice.config import VoiceConfig
from jarvis_brain.voice.events import hud_speak
from jarvis_brain.voice.resample import resample_pcm_s16le

EventSink = Callable[[Event], None]
PcmSink = Callable[[bytes, int], None]


class Synthesizer(Protocol):
    name: str
    sample_rate: int

    def speak(self, text: str, voice: str) -> bytes:
        """Return native-rate mono s16le PCM."""

    def stop(self) -> None:
        ...


@dataclass
class PcmChunk:
    pcm: bytes
    sample_rate: int


@dataclass
class LocalTTS:
    """Default local stack: Chatterbox via RealtimeTTS, Piper if it cannot load.

    Cloud engines are rejected in VoiceConfig. This class never imports ElevenLabs.
    """

    config: VoiceConfig
    on_event: EventSink | None = None
    on_pcm: PcmSink | None = None
    engine: Synthesizer | None = None
    active_voice: str = "jarvis"
    last_chunk: PcmChunk | None = None
    _stopped: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.engine is None:
            self.engine = self._load_engine()

    def _load_engine(self) -> Synthesizer:
        if self.config.provider == "chatterbox":
            try:
                return ChatterboxRealtimeSynthesizer(self.config)
            except Exception:
                if self.config.fallback == "piper":
                    return PiperSynthesizer(self.config)
                raise
        return PiperSynthesizer(self.config)

    def speak_text(
        self,
        text: str,
        *,
        voice: str = "current",
        interrupt: bool = False,
    ) -> PcmChunk:
        resolved = self.active_voice if voice == "current" else voice
        if resolved not in {"jarvis", "companion"}:
            resolved = "jarvis"
        self.active_voice = resolved
        if interrupt:
            self.stop()
        cleaned = clean_for_tts(text)
        if not cleaned:
            return PcmChunk(b"", self.config.client_sample_rate)
        if self.on_event:
            self.on_event(
                hud_speak(cleaned, voice=resolved, interrupt=interrupt)
            )
        native_rate = (
            getattr(self.engine, "sample_rate", None)
            or self.config.native_sample_rate
        )
        native = b""
        if self.engine:
            if self.engine.name == "chatterbox":
                for sentence in split_sentences(cleaned):
                    native += self.engine.speak(sentence, resolved)
            else:
                native = self.engine.speak(cleaned, resolved)
        pcm = resample_pcm_s16le(
            native, int(native_rate), self.config.client_sample_rate
        )
        if self.on_pcm and pcm:
            self.on_pcm(pcm, self.config.client_sample_rate)
        chunk = PcmChunk(pcm, self.config.client_sample_rate)
        self.last_chunk = chunk
        return chunk

    def speak_stream(
        self,
        deltas: Iterable[str],
        *,
        voice: str = "current",
        interrupt: bool = False,
    ) -> PcmChunk:
        combined = "".join(deltas)
        return self.speak_text(combined, voice=voice, interrupt=interrupt)

    def stop(self) -> None:
        self._stopped = True
        if self.engine:
            self.engine.stop()


class ChatterboxRealtimeSynthesizer:
    """Chatterbox Turbo/Nano via the official Python API.

    RealtimeTTS's ChatterboxEngine (0.8.5) wraps the same generate() and is
    the streaming *layer* when Hermes deltas are wired to TextToAudioStream.
    That engine does not accept nano=True, so we load ChatterboxTurboTTS here.
    Each speak() is one full clip (issue #528 streaming API is not merged).
    """

    name = "chatterbox"
    sample_rate = 24000

    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self._model: Any = None
        self._load()

    def _load(self) -> None:
        try:
            from chatterbox.tts_turbo import ChatterboxTurboTTS  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "Install the local extra: pip install -e '.[tts]' "
                "(realtimetts[chatterbox] only — not [all])."
            ) from exc
        nano = self.config.model == "nano"
        device = self.config.device
        if self.config.model_path:
            try:
                self._model = ChatterboxTurboTTS.from_local(
                    self.config.model_path, device=device, nano=nano
                )
            except TypeError:
                self._model = ChatterboxTurboTTS.from_local(
                    self.config.model_path, device=device
                )
            return
        try:
            self._model = ChatterboxTurboTTS.from_pretrained(
                device=device, nano=nano
            )
        except TypeError:
            self._model = ChatterboxTurboTTS.from_pretrained(device=device)

    def speak(self, text: str, voice: str) -> bytes:
        wav_path = _voice_wav(self.config, voice)
        if wav_path:
            self._model.prepare_conditionals(wav_path)
        wav = self._model.generate(text)
        return _torch_wav_to_s16le(wav)

    def stop(self) -> None:
        return


class PiperSynthesizer:
    """Official Piper binary (MIT). Not novik133's GPL copy."""

    name = "piper"

    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self.sample_rate = 22050
        self._load_rate()

    def _load_rate(self) -> None:
        import json
        from pathlib import Path

        model = self.config.piper_model
        if not model:
            return
        meta = Path(str(model) + ".json")
        if not meta.is_file():
            return
        try:
            data = json.loads(meta.read_text())
            self.sample_rate = int((data.get("audio") or {}).get("sample_rate") or 22050)
        except (OSError, ValueError, TypeError):
            return

    def speak(self, text: str, voice: str) -> bytes:
        import os
        import shutil
        import subprocess
        from pathlib import Path

        if not shutil.which(self.config.piper_bin) and not Path(self.config.piper_bin).is_file():
            raise FileNotFoundError(
                f"Piper binary {self.config.piper_bin!r} not on PATH. "
                "Run brain/scripts/setup_piper.sh or keep Chatterbox available."
            )
        if not self.config.piper_model:
            raise FileNotFoundError(
                "JARVIS_PIPER_MODEL is unset. Download a rhasspy/piper-voices .onnx."
            )
        cmd = [
            self.config.piper_bin,
            "--model",
            self.config.piper_model,
            "--output_raw",
            "--quiet",
        ]
        if self.config.piper_espeak_data:
            cmd.extend(["--espeak_data", self.config.piper_espeak_data])
        env = os.environ.copy()
        piper_dir = Path(self.config.piper_bin).resolve().parent
        lib_dir = piper_dir
        if lib_dir.is_dir():
            env["LD_LIBRARY_PATH"] = (
                f"{lib_dir}{os.pathsep}{env.get('LD_LIBRARY_PATH', '')}"
            )
        proc = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            capture_output=True,
            check=False,
            env=env,
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(err or f"piper exited {proc.returncode}")
        return proc.stdout

    def stop(self) -> None:
        return


def _voice_wav(config: VoiceConfig, voice: str) -> str | None:
    if voice == "companion":
        return config.companion_wav or config.jarvis_wav
    return config.jarvis_wav


def _torch_wav_to_s16le(wav: Any) -> bytes:
    try:
        import numpy as np
    except ImportError:
        data = wav.detach().cpu().flatten().tolist() if hasattr(wav, "detach") else list(wav)
        out = bytearray()
        for sample in data:
            s = max(-1.0, min(1.0, float(sample)))
            out.extend(int(s * 32767).to_bytes(2, "little", signed=True))
        return bytes(out)
    arr = wav.detach().cpu().numpy().reshape(-1) if hasattr(wav, "detach") else np.asarray(wav)
    clipped = np.clip(arr, -1.0, 1.0)
    return (clipped * 32767).astype("<i2").tobytes()
