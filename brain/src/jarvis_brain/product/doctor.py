from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

from jarvis_brain.auth.howdy import AuthGate
from jarvis_brain.ha.client import load_ha_config
from jarvis_brain.product.setup import load_product
from jarvis_brain.product.start import chrome_bin, desktop_bin, hermes_bin, kiosk_script, repo_root
from jarvis_brain.voice.config import VoiceConfig, resolve_voice_wav


def _check(id: str, ok: bool, detail: str, *, required: bool = False) -> dict[str, Any]:
    return {"id": id, "ok": ok, "required": required, "detail": detail}


def collect_checks() -> list[dict[str, Any]]:
    root = repo_root()
    product = load_product()
    py_ok = sys.version_info >= (3, 11)
    checks = [
        _check(
            "python",
            py_ok,
            f"{sys.version.split()[0]} ({sys.executable})",
            required=True,
        ),
        _check(
            "repo",
            (root / "desktop" / "ui" / "index.html").is_file(),
            str(root),
            required=True,
        ),
    ]

    piper_bin = shutil.which("piper")
    try:
        voice = VoiceConfig.from_env()
        piper_path = voice.piper_bin
        piper_model = voice.piper_model
    except Exception as exc:
        piper_path = None
        piper_model = None
        voice_err = str(exc)
    else:
        voice_err = None
    piper_ok = bool(
        (piper_path and Path(str(piper_path)).is_file())
        or piper_bin
    ) and bool(piper_model and Path(str(piper_model)).is_file())
    checks.append(
        _check(
            "piper",
            piper_ok,
            voice_err
            or (
                f"{piper_path or piper_bin} · {piper_model}"
                if piper_ok
                else "falta setup_piper.sh (voz local)"
            ),
            required=False,
        )
    )

    hermes = hermes_bin()
    checks.append(
        _check(
            "hermes",
            bool(hermes),
            hermes or "falta Hermes (bash scripts/install-hermes.sh)",
            required=True,
        )
    )

    tauri = desktop_bin()
    kiosk = kiosk_script()
    chrome = chrome_bin()
    hud_ok = bool(tauri) or (bool(kiosk) and bool(chrome))
    if tauri:
        hud_detail = f"tauri {tauri}"
    elif kiosk and chrome:
        hud_detail = f"kiosk {chrome}"
    elif kiosk:
        hud_detail = "kiosk listo, falta Chromium"
    else:
        hud_detail = "ni Tauri ni kiosk"
    checks.append(_check("hud", hud_ok, hud_detail, required=True))

    wav = resolve_voice_wav("jarvis")
    checks.append(
        _check(
            "voices",
            bool(wav and Path(wav).is_file()),
            wav or "sin jarvis.wav (placeholder en voices/)",
        )
    )

    auth = AuthGate()
    st = auth.status()
    checks.append(
        _check(
            "howdy",
            st.enrolled,
            f"{'compare.py' if st.enrolled else 'no enrolado'} · cam {st.camera}",
        )
    )
    checks.append(
        _check(
            "camera",
            st.camera != "missing",
            st.camera,
        )
    )

    ha = load_ha_config()
    checks.append(
        _check(
            "ha",
            ha.configured,
            ha.url if ha.configured else "HA_URL / HA_TOKEN o ~/.config/jarvis/ha.env",
        )
    )

    detect = os.environ.get("JARVIS_YOLO_DETECT") or str(
        Path.home() / ".local/share/jarvis/detect.py"
    )
    checks.append(
        _check(
            "door",
            Path(detect).is_file(),
            detect if Path(detect).is_file() else "sin detect.py fuera del árbol",
        )
    )

    tesseract = shutil.which("tesseract")
    checks.append(_check("tesseract", bool(tesseract), tesseract or "apt: tesseract-ocr tesseract-ocr-spa"))

    mode = f"{product.mode} · {product.provider}" if product else "sin setup (jarvis setup --demo)"
    checks.append(_check("product", product is not None, mode, required=True))

    host = os.environ.get("JARVIS_BUS_HOST", "127.0.0.1")
    checks.append(
        _check(
            "bind",
            host in {"127.0.0.1", "localhost"},
            f"JARVIS_BUS_HOST={host}",
            required=True,
        )
    )
    return checks


def doctor_report() -> dict[str, Any]:
    checks = collect_checks()
    required_ok = all(c["ok"] for c in checks if c["required"])
    return {
        "ok": required_ok,
        "ready": required_ok,
        "checks": checks,
        "next": (
            "jarvis start"
            if required_ok
            else "Revisa los [!!]. Guía: docs/POPOS.md"
        ),
    }


def format_doctor(report: dict[str, Any] | None = None) -> str:
    data = report or doctor_report()
    lines = ["JARVIS doctor · Pop!_OS"]
    for item in data["checks"]:
        mark = "ok" if item["ok"] else ("!!" if item["required"] else "--")
        lines.append(f"  [{mark}] {item['id']}: {item['detail']}")
    lines.append("listo" if data["ready"] else "no listo")
    lines.append(str(data["next"]))
    return "\n".join(lines)
