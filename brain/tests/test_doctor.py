from jarvis_brain.config import BrainConfig
from jarvis_brain.product.doctor import collect_checks, doctor_report, format_doctor
from jarvis_brain.product.start import kiosk_script, launch_hud, repo_root


def test_default_bind_is_loopback() -> None:
    assert BrainConfig.from_env().bus_host == "127.0.0.1"


def test_doctor_report_shape() -> None:
    report = doctor_report()
    ids = {c["id"] for c in report["checks"]}
    assert {"python", "repo", "hermes", "hud", "product", "bind"} <= ids
    assert "ready" in report
    text = format_doctor(report)
    assert "JARVIS doctor" in text
    assert any(c["id"] == "repo" and c["ok"] for c in report["checks"])
    assert any(c["id"] == "hud" and c["ok"] for c in report["checks"])


def test_kiosk_script_in_repo() -> None:
    script = kiosk_script()
    assert script is not None
    assert script.is_file()
    assert "firefox" in script.read_text()
    assert (repo_root() / "docs" / "POPOS.md").is_file()
    assert (repo_root() / "scripts" / "popos-trial.sh").is_file()


def test_launch_hud_kiosk_without_chrome(monkeypatch) -> None:
    monkeypatch.setattr("jarvis_brain.product.start.desktop_bin", lambda: None)
    monkeypatch.setattr("jarvis_brain.product.start.chrome_bin", lambda: None)
    try:
        launch_hud(brain_url="http://127.0.0.1:8765", prefer="kiosk")
    except RuntimeError as exc:
        assert "kiosk" in str(exc).lower() or "Firefox" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_collect_bind_required() -> None:
    checks = {c["id"]: c for c in collect_checks()}
    assert checks["bind"]["required"] is True
    assert checks["bind"]["ok"] is True
