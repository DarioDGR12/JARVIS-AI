from __future__ import annotations

from typing import Any

ZONES = (
    ("luces", ("light", "switch"), "Luces"),
    ("clima", ("climate", "fan"), "Clima"),
    ("puertas", ("lock", "cover", "binary_sensor"), "Puertas"),
    ("media", ("media_player",), "Media"),
)


def _on(state: str) -> bool:
    return str(state or "").lower() in {"on", "open", "unlocked", "home", "heat", "cool"}


def build_schematic(states: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Domain buckets for a house diagram. Not the HA frontend."""
    rows = list(states or [])
    zones: list[dict[str, Any]] = []
    for zone_id, domains, label in ZONES:
        members = [
            {
                "entity_id": str(s.get("entity_id") or ""),
                "name": str(s.get("name") or s.get("entity_id") or ""),
                "state": str(s.get("state") or ""),
                "on": _on(str(s.get("state") or "")),
            }
            for s in rows
            if str(s.get("entity_id") or "").split(".", 1)[0] in domains
        ]
        zones.append(
            {
                "id": zone_id,
                "label": label,
                "count": len(members),
                "on": sum(1 for m in members if m["on"]),
                "members": members[:12],
            }
        )
    return {
        "configured": bool(rows),
        "zones": zones,
        "total": len(rows),
    }
