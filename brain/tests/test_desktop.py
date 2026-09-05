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
    assert 'id="map-slot"' in html
    assert 'id="cam-home"' in html
    assert 'id="cam-vision"' in html
    assert 'id="btn-capture"' in html
    assert 'id="cam-device"' in html
    assert 'id="btn-cam-home"' in html
    assert 'id="btn-visor"' in html
    assert 'id="btn-overlay"' in html
    assert 'id="ha-schematic"' in html
    assert 'id="ha-rooms"' in html
    assert 'id="screen-regions"' in html
    assert "gestures.js" in html
    assert 'id="btn-mic"' in html
    assert 'id="btn-through"' in html
    assert 'id="btn-arm"' in html
    assert 'id="screen-highlight"' in html
    rust = (root / "desktop" / "src-tauri" / "src" / "lib.rs").read_text()
    assert "set_visor" in rust
    assert "set_overlay" in rust
    assert "spawn_overlay_hit_loop" in rust
    assert "set_click_through" in rust
    assert "set_ignore_cursor_events" in rust
    assert "set_background_color" in rust
    assert "spawn_hit_loop" in rust
    caps = (root / "desktop" / "src-tauri" / "capabilities" / "default.json").read_text()
    assert "allow-set-ignore-cursor-events" in caps
    assert "allow-set-background-color" in caps
    assert "allow-cursor-position" in caps
    assert "cam-hold-banner" in html
    js = (root / "desktop" / "ui" / "app.js").read_text()
    assert "getUserMedia" in js
    assert "releaseForHowdy" in js
    assert "/api/hud/camera" in js
    assert "patchMetaCam" in js
    assert "bargeIn" in js
    assert "SpeechRecognition" in js
    assert "/api/voice/transcript" in js
    assert "playLive" in js
    assert "startPcm" in js
    assert "last_selection" in js
    assert "paintSchematic" in js
    assert "jarvisHud" in js
    assert "paintRegions" in js
    assert "hls.min.js" in js
    assert 'id="live-video"' in html
    globe = root / "desktop" / "ui" / "globe"
    assert (globe / "vendor" / "hls.min.js").is_file()
    assert '"hls"' in (globe / "feeds.json").read_text()
    assert "nasaplus.akamaized.net" in (globe / "feeds.json").read_text()
    assert '"jwst"' in (globe / "feeds.json").read_text()
    assert (root / "desktop" / "ui" / "overlay.html").is_file()
    overlay = (root / "desktop" / "ui" / "overlay.html").read_text()
    assert "data-tauri-drag-region" in overlay
    assert (root / "desktop" / "ui" / "gestures.js").is_file()
    assert "nudgeDist" in (root / "desktop" / "ui" / "globe" / "globe.js").read_text()
    assert (root / "deploy" / "systemd" / "jarvis-brain.service").is_file()
    assert (root / "deploy" / "kiosk" / "jarvis-kiosk.sh").is_file()
    assert (root / "voices" / "jarvis.wav").is_file()
    assert (root / "brain" / "scripts" / "detect_template.py").is_file()
    assert (root / "docs" / "DETECT.md").is_file()
    csp = (root / "desktop" / "src-tauri" / "tauri.conf.json").read_text()
    assert "transparent" in csp
    assert "media-src" in csp and "https:" in csp
    assert (root / "brain" / "scripts" / "detect_stub.py").is_file()
    assert (globe / "index.html").is_file()
    assert (globe / "globe.js").is_file()
    assert (globe / "vendor" / "three.min.js").is_file()
    assert (globe / "feeds.json").is_file()
    assert (globe / "textures" / "earth.jpg").is_file()
    assert "textures/earth.jpg" in (globe / "globe.js").read_text()
    assert "Blue Marble" in (globe / "NOTICE.md").read_text()
    notice = (globe / "NOTICE.md").read_text()
    assert "sentinel-feed-grid" in notice
    assert "do **not** vendor" in notice
    csp = (root / "desktop" / "src-tauri" / "tauri.conf.json").read_text()
    assert "ws://127.0.0.1:*" in csp
    assert "frame-src 'self'" in csp
    assert "mediastream:" in csp


def test_desktop_bin_honors_env(tmp_path: Path, monkeypatch) -> None:
    fake = tmp_path / "jarvis-desktop"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("JARVIS_DESKTOP_BIN", str(fake))
    assert desktop_bin() == fake
