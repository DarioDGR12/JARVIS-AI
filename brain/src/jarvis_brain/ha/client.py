from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from jarvis_brain.product.setup import product_dir


@dataclass(frozen=True)
class HAConfig:
    url: str
    token: str

    @property
    def configured(self) -> bool:
        return bool(self.url and self.token)


def load_ha_config() -> HAConfig:
    url = os.environ.get("HA_URL") or os.environ.get("JARVIS_HA_URL") or ""
    token = os.environ.get("HA_TOKEN") or os.environ.get("JARVIS_HA_TOKEN") or ""
    path = product_dir() / "ha.env"
    if path.is_file():
        for raw in path.read_text().splitlines():
            if "=" in raw and not raw.strip().startswith("#"):
                key, value = raw.split("=", 1)
                key, value = key.strip(), value.strip()
                if key in {"HA_URL", "JARVIS_HA_URL"} and not url:
                    url = value
                if key in {"HA_TOKEN", "JARVIS_HA_TOKEN"} and not token:
                    token = value
    return HAConfig(url=url.rstrip("/"), token=token)


class HomeAssistant:
    """LAN client. Writes go through services, never POST /api/states."""

    def __init__(self, cfg: HAConfig | None = None) -> None:
        self.cfg = cfg or load_ha_config()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.cfg.token}",
            "Content-Type": "application/json",
        }

    def ping(self) -> bool:
        if not self.cfg.configured:
            return False
        try:
            r = httpx.get(
                f"{self.cfg.url}/api/",
                headers=self._headers(),
                timeout=3.0,
            )
            return r.status_code < 400
        except Exception:
            return False

    def states(self) -> list[dict]:
        if not self.cfg.configured:
            raise RuntimeError("Home Assistant is not configured (HA_URL / HA_TOKEN).")
        r = httpx.get(
            f"{self.cfg.url}/api/states",
            headers=self._headers(),
            timeout=8.0,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    def call(
        self,
        domain: str,
        service: str,
        *,
        entity_id: str | None = None,
        data: dict | None = None,
    ) -> dict:
        if not self.cfg.configured:
            raise RuntimeError("Home Assistant is not configured (HA_URL / HA_TOKEN).")
        body = dict(data or {})
        if entity_id:
            body["entity_id"] = entity_id
        r = httpx.post(
            f"{self.cfg.url}/api/services/{domain}/{service}",
            headers=self._headers(),
            json=body,
            timeout=8.0,
        )
        r.raise_for_status()
        return {"ok": True, "status": r.status_code, "body": r.json() if r.content else None}

    def status_line(self) -> str:
        if not self.cfg.configured:
            return "Casa no configurada. URL y token en la vista Casa."
        try:
            states = self.states()
        except Exception as exc:
            return f"Casa no responde: {exc}"
        lights = [
            s
            for s in states
            if str(s.get("entity_id") or "").startswith("light.")
        ]
        on = [s for s in lights if s.get("state") == "on"]
        return f"Casa: {len(states)} entidades, {len(on)}/{len(lights)} luces encendidas."


def write_ha_config(url: str, token: str) -> Path:
    dest = product_dir()
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "ha.env"
    path.write_text(f"HA_URL={url.rstrip('/')}\nHA_TOKEN={token}\n")
    path.chmod(0o600)
    return path
