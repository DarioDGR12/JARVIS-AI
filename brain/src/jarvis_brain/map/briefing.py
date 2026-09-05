from __future__ import annotations

from typing import Any

from jarvis_brain.map.feeds import load_feeds, query_feeds, resolve_place


def brief_world(q: str | None = None, feeds: list[dict[str, Any]] | None = None) -> str:
    """Offline SENTINEL extract. Live YT/HLS is a later round."""
    catalog = feeds if feeds is not None else load_feeds()
    needle = (q or "").strip()
    place = resolve_place(needle) if needle else None
    if place:
        hits = query_feeds(catalog, place["id"]) or query_feeds(catalog, place["loc"])
        if not hits:
            hits = [
                {
                    "loc": place["loc"],
                    "country": place.get("country") or "",
                    "lat": place["lat"],
                    "lon": place["lon"],
                    "id": place["id"],
                }
            ]
        title = f"Briefing {place['loc']}"
    elif needle:
        hits = query_feeds(catalog, needle)
        title = f"Briefing «{needle}»"
    else:
        hits = catalog[:8]
        title = "Briefing SENTINEL"
    if not hits:
        return f"{title}: sin pines en el extracto offline."
    lines = [f"{title} · {len(hits)} pines (extracto, no live):"]
    for feed in hits[:8]:
        loc = feed.get("loc") or feed.get("id")
        country = feed.get("country") or ""
        lat = feed.get("lat")
        lon = feed.get("lon")
        geo = f"{lat:.2f},{lon:.2f}" if isinstance(lat, (int, float)) else ""
        lines.append(f"- {loc} {country} {geo}".strip())
    return "\n".join(lines)
