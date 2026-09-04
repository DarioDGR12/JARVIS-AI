from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx

from jarvis_brain.product.setup import hermes_home, load_product


def hermes_bin() -> str | None:
    env = os.environ.get("HERMES_BIN")
    if env and Path(env).is_file():
        return env
    for cand in (
        Path("/tmp/hermes-agent-src/.venv/bin/hermes"),
        Path.home() / ".local/bin/hermes",
    ):
        if cand.is_file():
            return str(cand)
    return shutil.which("hermes")


def hermes_up(url: str, key: str) -> bool:
    try:
        r = httpx.get(
            f"{url.rstrip('/')}/health",
            headers={"Authorization": f"Bearer {key}"},
            timeout=2.0,
        )
        return r.status_code < 400
    except Exception:
        return False


def mock_up() -> bool:
    try:
        r = httpx.get("http://127.0.0.1:18765/health", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False


def ensure_demo_stack(brain_root: Path, hermes_key: str) -> None:
    """Start mock LLM + Hermes if this is demo mode and they are down."""
    product = load_product()
    if product and product.mode != "demo":
        return
    mock = brain_root / "scripts" / "mock_openai_llm.py"
    if mock.is_file() and not mock_up():
        subprocess.Popen(
            ["python3", str(mock)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.3)
    if hermes_up(os.environ.get("JARVIS_HERMES_URL", "http://127.0.0.1:8642"), hermes_key):
        return
    bin_path = hermes_bin()
    if not bin_path:
        raise RuntimeError(
            "Hermes not installed. Clone NousResearch/hermes-agent and `uv sync --no-dev`, "
            "or set HERMES_BIN."
        )
    env = os.environ.copy()
    env["API_SERVER_ENABLED"] = "true"
    env["API_SERVER_KEY"] = hermes_key
    env["API_SERVER_HOST"] = "127.0.0.1"
    env["API_SERVER_PORT"] = "8642"
    log = hermes_home() / "logs"
    log.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [bin_path, "gateway", "run", "--replace"],
        env=env,
        stdout=open(log / "gateway.stdout", "ab"),
        stderr=subprocess.STDOUT,
    )
    url = "http://127.0.0.1:8642"
    for _ in range(40):
        if hermes_up(url, hermes_key):
            return
        time.sleep(0.25)
    raise RuntimeError("Hermes API did not start on :8642")
