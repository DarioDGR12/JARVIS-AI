from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from pathlib import Path

import httpx

from jarvis_brain.product.setup import hermes_home, load_product, product_file


STAMP_NAME = "jarvis.gateway.stamp"
PID_NAME = "jarvis.gateway.pid"


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
    return shutil_which("hermes")


def shutil_which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


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


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def console_already_up(port: int) -> bool:
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/api/status", timeout=1.0)
        data = r.json()
        return r.status_code == 200 and "hermes" in data and "product" in data
    except Exception:
        return False


def stamp_path() -> Path:
    return hermes_home() / STAMP_NAME


def pid_path() -> Path:
    return hermes_home() / PID_NAME


def watched_config_paths() -> list[Path]:
    return [hermes_home() / "config.yaml", hermes_home() / ".env", product_file()]


def newest_config_mtime() -> float:
    times = [0.0]
    for path in watched_config_paths():
        if path.is_file():
            times.append(path.stat().st_mtime)
    return max(times)


def hermes_config_stale() -> bool:
    """True when Hermes must be (re)started to pick up setup."""
    stamp = stamp_path()
    if not stamp.is_file():
        return True
    return newest_config_mtime() > stamp.stat().st_mtime + 0.01


def should_start_mock() -> bool:
    product = load_product()
    return product is None or product.mode == "demo"


def _load_hermes_dotenv() -> dict[str, str]:
    env_path = hermes_home() / ".env"
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for raw in env_path.read_text().splitlines():
        if "=" in raw and not raw.strip().startswith("#"):
            key, value = raw.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _write_stamp(pid: int | None = None) -> None:
    home = hermes_home()
    home.mkdir(parents=True, exist_ok=True)
    stamp_path().write_text(str(time.time()))
    if pid:
        pid_path().write_text(str(pid))


def _pids_to_stop() -> set[int]:
    pids: set[int] = set()
    stored = pid_path()
    if stored.is_file():
        raw = stored.read_text().strip()
        if raw.isdigit():
            pids.add(int(raw))
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", r"hermes.*gateway"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in out.split():
            if line.isdigit():
                pids.add(int(line))
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    pids.discard(os.getpid())
    return pids


def stop_hermes() -> None:
    pids = _pids_to_stop()
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except PermissionError:
            continue
    deadline = time.time() + 4
    while time.time() < deadline and pids:
        alive: set[int] = set()
        for pid in pids:
            try:
                os.kill(pid, 0)
                alive.add(pid)
            except ProcessLookupError:
                continue
        pids = alive
        if not pids:
            break
        time.sleep(0.15)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    if pid_path().is_file():
        pid_path().unlink()


def start_hermes(hermes_key: str) -> None:
    bin_path = hermes_bin()
    if not bin_path:
        raise RuntimeError(
            "Hermes Agent is not installed. JARVIS uses it as the engine.\n"
            "Install once: git clone --depth 1 https://github.com/NousResearch/hermes-agent.git "
            "&& cd hermes-agent && uv sync --no-dev\n"
            "Then: export HERMES_BIN=/path/to/.venv/bin/hermes"
        )
    env = os.environ.copy()
    env.update(_load_hermes_dotenv())
    key = hermes_key if len(hermes_key) >= 16 else env.get(
        "API_SERVER_KEY", "jarvis-phase1-key"
    )
    if len(key) < 16:
        key = "jarvis-phase1-key"
    env["API_SERVER_ENABLED"] = "true"
    env["API_SERVER_KEY"] = key
    env["API_SERVER_HOST"] = env.get("API_SERVER_HOST", "127.0.0.1")
    env["API_SERVER_PORT"] = env.get("API_SERVER_PORT", "8642")
    log = hermes_home() / "logs"
    log.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [bin_path, "gateway", "run", "--replace"],
        env=env,
        stdout=open(log / "gateway.stdout", "ab"),
        stderr=subprocess.STDOUT,
    )
    url = f"http://{env['API_SERVER_HOST']}:{env['API_SERVER_PORT']}"
    for _ in range(48):
        if hermes_up(url, key):
            _write_stamp(proc.pid)
            return
        if proc.poll() is not None:
            break
        time.sleep(0.25)
    raise RuntimeError(
        "Hermes API did not start on :8642. "
        "API_SERVER_KEY must be at least 16 characters. "
        f"See {log / 'gateway.stdout'}"
    )


def ensure_mock(brain_root: Path) -> None:
    mock = brain_root / "scripts" / "mock_openai_llm.py"
    if not mock.is_file() or mock_up():
        return
    subprocess.Popen(
        ["python3", str(mock)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        if mock_up():
            return
        time.sleep(0.1)
    raise RuntimeError("Demo model did not start on :18765")


def ensure_stack(brain_root: Path, hermes_key: str) -> None:
    """Bring up the local engine the product needs. Restarts Hermes after setup."""
    if should_start_mock():
        ensure_mock(brain_root)
    url = os.environ.get("JARVIS_HERMES_URL", "http://127.0.0.1:8642")
    up = hermes_up(url, hermes_key)
    if up and not hermes_config_stale():
        return
    if up:
        stop_hermes()
        time.sleep(0.2)
    start_hermes(hermes_key)


def ensure_demo_stack(brain_root: Path, hermes_key: str) -> None:
    """Back-compat alias used by older call sites."""
    ensure_stack(brain_root, hermes_key)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def desktop_bin() -> Path | None:
    env = os.environ.get("JARVIS_DESKTOP_BIN")
    if env and Path(env).is_file():
        return Path(env)
    root = repo_root()
    for cand in (
        root / "desktop" / "src-tauri" / "target" / "debug" / "jarvis-desktop",
        root / "desktop" / "src-tauri" / "target" / "release" / "jarvis-desktop",
        Path.home() / ".local" / "bin" / "jarvis-desktop",
    ):
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    found = shutil_which("jarvis-desktop")
    return Path(found) if found else None


def launch_desktop(*, brain_url: str) -> subprocess.Popen:
    binary = desktop_bin()
    if binary is None:
        raise RuntimeError(
            "JARVIS desktop app is not built.\n"
            "From the repo: bash scripts/install.sh\n"
            "Or: cd desktop && npm install && npx tauri build"
        )
    env = os.environ.copy()
    env["JARVIS_BRAIN_URL"] = brain_url
    env.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")
    return subprocess.Popen([str(binary)], env=env)
