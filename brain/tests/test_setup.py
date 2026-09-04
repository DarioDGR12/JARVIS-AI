from pathlib import Path

import pytest

from jarvis_brain.product.setup import apply_setup, load_product


def _homes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "jarvis"))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))


def test_setup_demo_writes_mock_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _homes(tmp_path, monkeypatch)
    product = apply_setup(provider="demo", api_key="sk-local")
    assert product.mode == "demo"
    cfg = (tmp_path / "hermes" / "config.yaml").read_text()
    assert "mock-jarvis" in cfg
    assert "127.0.0.1:18765" in cfg
    env = (tmp_path / "hermes" / ".env").read_text()
    assert "API_SERVER_ENABLED=true" in env
    loaded = load_product()
    assert loaded is not None and loaded.provider == "demo"


def test_byok_key_stays_out_of_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _homes(tmp_path, monkeypatch)
    secret = "sk-testkey123456789"
    apply_setup(provider="openai", api_key=secret, model="gpt-4o-mini")
    yaml = (tmp_path / "hermes" / "config.yaml").read_text()
    assert secret not in yaml
    assert "provider: openai" in yaml
    env = (tmp_path / "hermes" / ".env").read_text()
    assert f"OPENAI_API_KEY={secret}" in env
    mode = oct((tmp_path / "hermes" / ".env").stat().st_mode)[-3:]
    assert mode == "600"


def test_rejects_bad_openai_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _homes(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        apply_setup(provider="openai", api_key="not-a-real-key")
