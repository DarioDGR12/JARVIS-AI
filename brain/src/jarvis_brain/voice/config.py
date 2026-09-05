from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


CLOUD_TTS_BLOCKLIST = frozenset(
    {
        "elevenlabs",
        "openai",
        "openai_tts",
        "edge",
        "edge_tts",
        "gtts",
        "resemble",
        "resemble_cloud",
        "azure",
    }
)

LOCAL_PROVIDERS = frozenset({"chatterbox", "piper"})


class CloudTtsBlocked(ValueError):
    """Raised if config tries to use a cloud TTS provider."""


@dataclass(frozen=True)
class VoiceConfig:
    """Local-only TTS. ElevenLabs is not a valid provider or fallback."""

    provider: str = "chatterbox"
    fallback: str = "piper"
    model: str = "turbo"
    device: str = "cuda"
    native_sample_rate: int = 24000
    client_sample_rate: int = 16000
    model_path: str | None = None
    jarvis_wav: str | None = None
    companion_wav: str | None = None
    piper_bin: str = "piper"
    piper_model: str | None = None
    piper_espeak_data: str | None = None
    offline: bool = True
    voices: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        provider = self.provider.lower()
        fallback = self.fallback.lower()
        if provider in CLOUD_TTS_BLOCKLIST or fallback in CLOUD_TTS_BLOCKLIST:
            raise CloudTtsBlocked(
                f"Cloud TTS is forbidden (provider={self.provider!r}, "
                f"fallback={self.fallback!r}). Use chatterbox + piper."
            )
        if provider not in LOCAL_PROVIDERS:
            raise CloudTtsBlocked(f"Unknown TTS provider {self.provider!r}")
        if fallback not in LOCAL_PROVIDERS:
            raise CloudTtsBlocked(f"Unknown TTS fallback {self.fallback!r}")

    @classmethod
    def from_env(cls) -> VoiceConfig:
        home = Path(
            os.environ.get(
                "JARVIS_PIPER_HOME",
                str(Path.home() / ".local/share/jarvis/piper"),
            )
        )
        default_bin = home / "piper" / "piper"
        default_model = home / "voices" / "es_ES-davefx-medium.onnx"
        default_espeak = home / "piper" / "espeak-ng-data"
        model_path = os.environ.get("JARVIS_CHATTERBOX_PATH") or None
        return cls(
            provider=os.environ.get("JARVIS_TTS_PROVIDER", "chatterbox"),
            fallback=os.environ.get("JARVIS_TTS_FALLBACK", "piper"),
            model=os.environ.get("JARVIS_CHATTERBOX_MODEL", "turbo"),
            device=_default_device(),
            model_path=model_path,
            jarvis_wav=_resolve_voice_wav("jarvis", os.environ.get("JARVIS_VOICE_JARVIS")),
            companion_wav=_resolve_voice_wav(
                "companion", os.environ.get("JARVIS_VOICE_COMPANION")
            ),
            piper_bin=os.environ.get("JARVIS_PIPER_BIN")
            or (str(default_bin) if default_bin.is_file() else "piper"),
            piper_model=os.environ.get("JARVIS_PIPER_MODEL")
            or (str(default_model) if default_model.is_file() else None),
            piper_espeak_data=os.environ.get("JARVIS_PIPER_ESPEAK")
            or (str(default_espeak) if default_espeak.is_dir() else None),
            offline=os.environ.get("HF_HUB_OFFLINE", "1") != "0",
        )


def _repo_voices() -> Path:
    return Path(__file__).resolve().parents[4] / "voices"


def resolve_voice_wav(name: str, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    candidates = (
        Path.home() / ".local/share/jarvis/voices" / f"{name}.wav",
        _repo_voices() / f"{name}.wav",
    )
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def _resolve_voice_wav(name: str, explicit: str | None) -> str | None:
    return resolve_voice_wav(name, explicit)


def _default_device() -> str:
    env = os.environ.get("JARVIS_TTS_DEVICE")
    if env:
        return env
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"
