from jarvis_brain.config import BrainConfig


def test_default_hermes_key_meets_hermes_guard() -> None:
    cfg = BrainConfig()
    assert len(cfg.hermes_api_key) >= 16
    assert "JARVIS_PHASE1_OK" in cfg.overlay
