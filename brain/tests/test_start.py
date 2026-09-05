import os
from pathlib import Path

import pytest

from jarvis_brain.product.setup import apply_setup, ensure_product_configured
from jarvis_brain.product.start import (
    hermes_config_stale,
    should_start_mock,
    stamp_path,
)


def _homes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "jarvis"))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))


def test_first_run_writes_demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _homes(tmp_path, monkeypatch)
    product, created = ensure_product_configured()
    assert created is True
    assert product.mode == "demo"
    again, created_again = ensure_product_configured()
    assert created_again is False
    assert again.provider == "demo"


def test_stale_until_stamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _homes(tmp_path, monkeypatch)
    apply_setup(provider="demo", api_key="sk-local")
    assert hermes_config_stale() is True
    stamp = stamp_path()
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text("ready")
    assert hermes_config_stale() is False
    env = tmp_path / "hermes" / ".env"
    env.write_text(env.read_text() + "OPENAI_API_KEY=sk-changed\n")
    stamp.touch()
    # config must be newer than the stamp we just refreshed
    later = stamp.stat().st_mtime + 5
    os.utime(env, (later, later))
    assert hermes_config_stale() is True


def test_mock_only_in_demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _homes(tmp_path, monkeypatch)
    apply_setup(provider="demo", api_key="sk-local")
    assert should_start_mock() is True
    apply_setup(provider="openai", api_key="sk-testkey123456789")
    assert should_start_mock() is False
