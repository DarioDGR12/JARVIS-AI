from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOM_TOKENS: dict[str, str] = {
    "cocina": "cocina",
    "kitchen": "cocina",
    "salon": "salon",
    "salón": "salon",
    "living": "salon",
    "lounge": "salon",
    "comedor": "comedor",
    "dining": "comedor",
    "dormitorio": "dormitorio",
    "recamara": "dormitorio",
    "bedroom": "dormitorio",
    "baño": "baño",
    "bano": "baño",
    "bathroom": "baño",
    "aseo": "baño",
    "oficina": "oficina",
    "office": "oficina",
    "despacho": "oficina",
    "garaje": "garaje",
    "garage": "garaje",
    "entrada": "entrada",
    "hall": "entrada",
    "pasillo": "pasillo",
    "terraza": "terraza",
    "patio": "patio",
    "jardin": "jardin",
    "jardín": "jardin",
    "garden": "jardin",
}


def load_room_map(path: Path | None = None) -> dict[str, str]:
    raw = path
    env = os.environ.get("JARVIS_HA_ROOMS")
    if raw is None and env:
        raw = Path(env)
    if raw is None:
        raw = Path.home() / ".config/jarvis/ha-rooms.json"
    if not raw.is_file():
        return {}
    try:
        data = json.loads(raw.read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if not str(k).startswith("_")}


def infer_room(
    entity_id: str,
    name: str | None = None,
    mapping: dict[str, str] | None = None,
) -> str:
    eid = str(entity_id or "")
    if mapping and eid in mapping:
        return mapping[eid]
    attrs_area = ""
    blob = f"{eid} {name or ''} {attrs_area}".lower()
    for token, room in ROOM_TOKENS.items():
        if token in blob:
            return room
    slug = eid.split(".", 1)[-1]
    first = slug.split("_", 1)[0].lower()
    if first in ROOM_TOKENS:
        return ROOM_TOKENS[first]
    return "otros"


def group_rooms(
    states: list[dict[str, Any]] | None,
    mapping: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    rooms: dict[str, dict[str, Any]] = {}
    for row in states or []:
        eid = str(row.get("entity_id") or "")
        if not eid:
            continue
        room = infer_room(eid, str(row.get("name") or "") or None, mapping)
        bucket = rooms.setdefault(
            room,
            {"id": room, "label": room.replace("_", " ").title(), "count": 0, "on": 0, "members": []},
        )
        on = str(row.get("state") or "").lower() in {
            "on",
            "open",
            "unlocked",
            "home",
            "heat",
            "cool",
        }
        bucket["count"] += 1
        if on:
            bucket["on"] += 1
        if len(bucket["members"]) < 8:
            bucket["members"].append(
                {
                    "entity_id": eid,
                    "name": str(row.get("name") or eid),
                    "state": str(row.get("state") or ""),
                    "on": on,
                }
            )
    order = [r for r in rooms.values() if r["id"] != "otros"] + (
        [rooms["otros"]] if "otros" in rooms else []
    )
    return order
