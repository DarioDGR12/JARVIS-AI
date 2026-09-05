from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jarvis_brain.bus.envelope import Event
from jarvis_brain.map.feeds import FEED_CAP, filter_feeds, load_feeds, query_feeds


@dataclass
class MapState:
    """Host-side SENTINEL state. The brain never imports Three.js."""

    mounted: bool = False
    ready: bool = False
    last_focus: dict[str, Any] | None = None
    last_query: str | None = None
    last_selection: dict[str, Any] | None = None
    last_error: str | None = None
    feeds: list[dict[str, Any]] = field(default_factory=list)
    visible: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.feeds:
            self.feeds = load_feeds()
            self.visible = list(self.feeds)

    def snapshot(self) -> dict[str, Any]:
        return {
            "mounted": self.mounted,
            "ready": self.ready,
            "last_focus": self.last_focus,
            "last_query": self.last_query,
            "last_selection": self.last_selection,
            "last_error": self.last_error,
            "count": len(self.visible),
            "cap": FEED_CAP,
            "source": "sentinel",
        }

    def apply(self, event: Event) -> None:
        payload = event.payload or {}
        if event.type == "hud.show_view":
            view = str(payload.get("view") or "")
            self.mounted = view == "map"
            if not self.mounted:
                self.ready = False
        elif event.type == "map.ready":
            self.ready = True
            self.mounted = True
            self.last_error = None
        elif event.type == "map.focus":
            self.last_focus = {
                "lat": payload.get("lat"),
                "lon": payload.get("lon"),
                "zoom": payload.get("zoom"),
            }
            self.visible = list(self.feeds)
        elif event.type == "map.query":
            self.last_query = str(payload.get("q") or "")
            self.visible = query_feeds(self.feeds, self.last_query)
        elif event.type == "map.show_feeds":
            self.visible = filter_feeds(
                self.feeds,
                region=payload.get("region"),
                tags=payload.get("tags"),
            )
        elif event.type == "map.selection":
            self.last_selection = {
                "lat": payload.get("lat"),
                "lon": payload.get("lon"),
                "feed_id": payload.get("feed_id"),
            }
        elif event.type == "map.live":
            feed_id = str(payload.get("id") or "iss")
            lives = [f for f in self.feeds if f.get("live")]
            if feed_id == "next":
                current = str((self.last_selection or {}).get("feed_id") or "")
                ids = [str(f.get("id")) for f in lives]
                if current in ids and len(ids) > 1:
                    feed_id = ids[(ids.index(current) + 1) % len(ids)]
                elif ids:
                    feed_id = ids[0]
            hit = next((f for f in self.feeds if str(f.get("id")) == feed_id), None)
            if hit is None:
                hit = next((f for f in lives), None)
            if hit:
                self.last_selection = {
                    "lat": hit.get("lat"),
                    "lon": hit.get("lon"),
                    "feed_id": hit.get("id"),
                    "live": True,
                }
                self.last_focus = {"lat": hit.get("lat"), "lon": hit.get("lon"), "zoom": 4}
        elif event.type == "map.feed_ready":
            if payload.get("count") is not None:
                pass
        elif event.type == "map.error":
            self.last_error = str(payload.get("reason") or "error")
