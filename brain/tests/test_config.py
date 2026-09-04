from jarvis_brain.config import BrainConfig, build_overlay


def test_default_hermes_key_meets_hermes_guard() -> None:
    cfg = BrainConfig()
    assert len(cfg.hermes_api_key) >= 16
    assert "JARVIS" in cfg.overlay
    assert "JARVIS_PHASE1_OK" not in cfg.overlay


def test_qa_overlay_opt_in(monkeypatch) -> None:
    assert "JARVIS_PHASE1_OK" in build_overlay(qa=True)
    monkeypatch.setenv("JARVIS_QA", "1")
    assert "JARVIS_PHASE1_OK" in BrainConfig.from_env().overlay
