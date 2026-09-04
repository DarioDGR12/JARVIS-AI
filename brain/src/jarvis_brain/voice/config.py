from __future__ import annotations

import os
from dataclasses import dataclass, field


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
        model_path = os.environ.get("JARVIS_CHATTERBOX_PATH") or None
        return cls(
            provider=os.environ.get("JARVIS_TTS_PROVIDER", "chatterbox"),
            fallback=os.environ.get("JARVIS_TTS_FALLBACK", "piper"),
            model=os.environ.get("JARVIS_CHATTERBOX_MODEL", "turbo"),
            device=os.environ.get("JARVIS_TTS_DEVICE", "cuda"),
            model_path=model_path,
            jarvis_wav=os.environ.get("JARVIS_VOICE_JARVIS") or None,
            companion_wav=os.environ.get("JARVIS_VOICE_COMPANION") or None,
            piper_bin=os.environ.get("JARVIS_PIPER_BIN", "piper"),
            offline=os.environ.get("HF_HUB_OFFLINE", "1") != "0",
        )
