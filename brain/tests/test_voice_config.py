import os

import pytest

from jarvis_brain.voice.config import CLOUD_TTS_BLOCKLIST, CloudTtsBlocked, VoiceConfig


def test_default_is_local_chatterbox() -> None:
    cfg = VoiceConfig()
    assert cfg.provider == "chatterbox"
    assert cfg.fallback == "piper"
    assert "elevenlabs" in CLOUD_TTS_BLOCKLIST


@pytest.mark.parametrize("provider", sorted(CLOUD_TTS_BLOCKLIST))
def test_cloud_provider_rejected(provider: str) -> None:
    with pytest.raises(CloudTtsBlocked):
        VoiceConfig(provider=provider)


@pytest.mark.parametrize("fallback", sorted(CLOUD_TTS_BLOCKLIST))
def test_cloud_fallback_rejected(fallback: str) -> None:
    with pytest.raises(CloudTtsBlocked):
        VoiceConfig(fallback=fallback)


def test_from_env_cannot_sneak_elevenlabs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_TTS_PROVIDER", "elevenlabs")
    with pytest.raises(CloudTtsBlocked):
        VoiceConfig.from_env()
    os.environ.pop("JARVIS_TTS_PROVIDER", None)
