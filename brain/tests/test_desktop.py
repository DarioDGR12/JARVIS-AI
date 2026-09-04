from pathlib import Path

from jarvis_brain.product.start import desktop_bin, repo_root


def test_repo_contains_tauri_app() -> None:
    root = repo_root()
    assert (root / "desktop" / "src-tauri" / "tauri.conf.json").is_file()
    assert (root / "desktop" / "ui" / "index.html").is_file()
    html = (root / "desktop" / "ui" / "index.html").read_text()
    assert "JARVIS" in html
    assert "Ajustes" in html or "settings" in html
    assert 'id="home-view"' in html
    assert 'data-view="map"' in html
    assert 'data-view="vision"' in html
    assert 'class="bar"' in html
    csp = (root / "desktop" / "src-tauri" / "tauri.conf.json").read_text()
    assert "ws://127.0.0.1:*" in csp


def test_desktop_bin_honors_env(tmp_path: Path, monkeypatch) -> None:
    fake = tmp_path / "jarvis-desktop"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("JARVIS_DESKTOP_BIN", str(fake))
    assert desktop_bin() == fake
