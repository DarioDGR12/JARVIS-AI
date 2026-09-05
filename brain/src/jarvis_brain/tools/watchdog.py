from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time

from jarvis_brain.tools.stats import system_stats

PROFILES = {
    "desk": {"load": 8.0, "ram": 93.0, "temp": 88.0},
    "server": {"load": 16.0, "ram": 97.0, "temp": 92.0},
}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _profile() -> dict[str, float]:
    name = (os.environ.get("JARVIS_PROFILE") or "desk").strip().lower()
    return PROFILES.get(name, PROFILES["desk"])


def parse_quiet_window(raw: str | None) -> tuple[dt_time, dt_time] | None:
    text = (raw or os.environ.get("JARVIS_WATCH_QUIET") or "").strip()
    if not text or text in {"0", "off", "none"}:
        return None
    try:
        start_s, end_s = text.split("-", 1)
        start = datetime.strptime(start_s.strip(), "%H:%M").time()
        end = datetime.strptime(end_s.strip(), "%H:%M").time()
    except ValueError:
        return None
    return start, end


def in_quiet_hours(now: datetime | None = None, window: str | None = None) -> bool:
    span = parse_quiet_window(window)
    if span is None:
        return False
    stamp = (now or datetime.now()).time()
    start, end = span
    if start <= end:
        return start <= stamp < end
    return stamp >= start or stamp < end


@dataclass
class Watchdog:
    """Proactive system officer. Speaks only when a threshold trips."""

    load_max: float = field(default_factory=lambda: _env_float("JARVIS_WATCH_LOAD", _profile()["load"]))
    ram_max: float = field(default_factory=lambda: _env_float("JARVIS_WATCH_RAM", _profile()["ram"]))
    temp_max: float = field(default_factory=lambda: _env_float("JARVIS_WATCH_TEMP", _profile()["temp"]))
    cooldown_s: float = field(default_factory=lambda: _env_float("JARVIS_WATCH_COOLDOWN", 120.0))
    _last: dict[str, float] = field(default_factory=dict)

    def check(self, stats: dict | None = None) -> list[dict]:
        snap = stats if stats is not None else system_stats()
        now = time.time()
        alerts: list[dict] = []
        load = snap.get("load") or []
        if load and float(load[0]) >= self.load_max:
            alerts.append(
                {
                    "id": "load",
                    "title": "carga",
                    "content": f"Load {load[0]:.2f} ≥ {self.load_max:.1f}",
                }
            )
        ram = snap.get("mem_used_pct")
        if ram is not None and float(ram) >= self.ram_max:
            alerts.append(
                {
                    "id": "ram",
                    "title": "memoria",
                    "content": f"RAM {ram}% ≥ {self.ram_max:.0f}%",
                }
            )
        temp = snap.get("cpu_temp_c")
        if temp is not None and float(temp) >= self.temp_max:
            alerts.append(
                {
                    "id": "temp",
                    "title": "térmico",
                    "content": f"{temp} °C ≥ {self.temp_max:.0f} °C",
                }
            )
        out: list[dict] = []
        for alert in alerts:
            noted = self.note(
                str(alert["id"]),
                str(alert["title"]),
                str(alert["content"]),
                tripped=True,
                now=now,
            )
            if noted:
                out.append(noted)
        return out

    def note(
        self,
        key: str,
        title: str,
        content: str,
        *,
        tripped: bool,
        now: float | None = None,
    ) -> dict | None:
        """Cooldown-gated custom alert (Hermes down, etc.)."""
        if not tripped:
            return None
        stamp = time.time() if now is None else now
        if stamp - self._last.get(key, 0) < self.cooldown_s:
            return None
        self._last[key] = stamp
        return {"id": key, "title": title, "content": content}
