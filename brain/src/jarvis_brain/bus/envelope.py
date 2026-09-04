from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class Event:
    type: str
    payload: dict[str, Any]
    source: str
    v: int = 1
    id: str = field(default_factory=lambda: uuid4().hex)
    ts: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    corr_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "v": self.v,
            "id": self.id,
            "ts": self.ts,
            "source": self.source,
            "type": self.type,
            "corr_id": self.corr_id,
            "payload": self.payload,
        }


def new_event(
    type: str,
    payload: dict[str, Any],
    *,
    source: str,
    corr_id: str | None = None,
) -> Event:
    return Event(type=type, payload=payload, source=source, corr_id=corr_id)
