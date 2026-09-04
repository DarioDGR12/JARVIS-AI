from pathlib import Path

from jarvis_brain.auth.howdy import AuthGate, SENSITIVE


def _script(tmp_path: Path, code: int) -> Path:
    path = tmp_path / "compare.py"
    path.write_text(f"import sys\nsys.exit({code})\n")
    return path


def test_ok_caches(tmp_path: Path) -> None:
    gate = AuthGate(compare=_script(tmp_path, 0), user="dario", ttl_s=60)
    first = gate.verify(reason="ha.command", tool="ha.command")
    assert first.ok and first.howdy_exit == 0
    assert gate.cached() is True
    second = gate.verify(reason="ha.command", tool="ha.command")
    assert second.ok and second.error == "none"


def test_no_model_fails_closed(tmp_path: Path) -> None:
    gate = AuthGate(compare=_script(tmp_path, 10), user="dario")
    result = gate.require("ha.command")
    assert result.ok is False
    assert result.error == "no_model"


def test_public_skips_howdy() -> None:
    gate = AuthGate(compare=None)
    result = gate.require("volume.up")
    assert result.ok is True
    assert "ha.command" in SENSITIVE


def test_missing_compare_fails_sensitive() -> None:
    gate = AuthGate(compare=None)
    result = gate.require("ha.command")
    assert result.ok is False
    assert result.error == "no_model"
    assert gate.status().enrolled is False
