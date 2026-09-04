from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jarvis_brain.product.start import repo_root

FEED_CAP = 80

CITIES: dict[str, tuple[float, float, str]] = {
    "madrid": (40.4168, -3.7038, "ES"),
    "barcelona": (41.3874, 2.1686, "ES"),
    "london": (51.5074, -0.1278, "GB"),
    "londres": (51.5074, -0.1278, "GB"),
    "paris": (48.8566, 2.3522, "FR"),
    "parís": (48.8566, 2.3522, "FR"),
    "berlin": (52.52, 13.405, "DE"),
    "berlín": (52.52, 13.405, "DE"),
    "rome": (41.9028, 12.4964, "IT"),
    "roma": (41.9028, 12.4964, "IT"),
    "tokyo": (35.6762, 139.6503, "JP"),
    "tokio": (35.6762, 139.6503, "JP"),
    "tokío": (35.6762, 139.6503, "JP"),
    "new york": (40.7128, -74.006, "US"),
    "nueva york": (40.7128, -74.006, "US"),
    "nyc": (40.7128, -74.006, "US"),
    "los angeles": (34.0522, -118.2437, "US"),
    "mexico": (19.4326, -99.1332, "MX"),
    "méxico": (19.4326, -99.1332, "MX"),
    "buenos aires": (-34.6037, -58.3816, "AR"),
    "sao paulo": (-23.5505, -46.6333, "BR"),
    "são paulo": (-23.5505, -46.6333, "BR"),
    "cairo": (30.0444, 31.2357, "EG"),
    "el cairo": (30.0444, 31.2357, "EG"),
    "nairobi": (-1.2921, 36.8219, "KE"),
    "sydney": (-33.8688, 151.2093, "AU"),
    "sídney": (-33.8688, 151.2093, "AU"),
    "singapore": (1.3521, 103.8198, "SG"),
    "singapur": (1.3521, 103.8198, "SG"),
    "seoul": (37.5665, 126.978, "KR"),
    "seul": (37.5665, 126.978, "KR"),
    "seúl": (37.5665, 126.978, "KR"),
    "dubai": (25.2048, 55.2708, "AE"),
    "dubái": (25.2048, 55.2708, "AE"),
    "istanbul": (41.0082, 28.9784, "TR"),
    "estambul": (41.0082, 28.9784, "TR"),
}


def feeds_path() -> Path:
    return repo_root() / "desktop" / "ui" / "globe" / "feeds.json"


def load_feeds(path: Path | None = None) -> list[dict[str, Any]]:
    src = path or feeds_path()
    if not src.is_file():
        return []
    raw = json.loads(src.read_text())
    if not isinstance(raw, list):
        return []
    return [item for item in (normalize_feed(x) for x in raw) if item][:FEED_CAP]


def normalize_feed(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    if raw.get("unavailable") or raw.get("invalidUrl") or raw.get("duplicate"):
        return None
    try:
        lat = float(raw["lat"])
        lon = float(raw["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "id": str(raw.get("id") or raw.get("loc") or f"{lat},{lon}"),
        "loc": str(raw.get("loc") or raw.get("id") or "feed"),
        "country": str(raw.get("country") or ""),
        "lat": lat,
        "lon": lon,
        "region": str(raw.get("region") or ""),
        "tags": [str(t) for t in (raw.get("tags") or [])],
    }


def filter_feeds(
    feeds: list[dict[str, Any]],
    *,
    region: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    region_n = (region or "").strip().lower()
    tag_set = {str(t).lower() for t in (tags or [])}
    out = []
    for feed in feeds:
        if region_n and str(feed.get("region") or "").lower() != region_n:
            continue
        feed_tags = {str(t).lower() for t in (feed.get("tags") or [])}
        if tag_set and not (tag_set & feed_tags):
            continue
        out.append(feed)
    return out[:FEED_CAP]


def query_feeds(feeds: list[dict[str, Any]], q: str) -> list[dict[str, Any]]:
    needle = (q or "").strip().lower()
    if not needle:
        return list(feeds)[:FEED_CAP]
    hits = []
    for feed in feeds:
        blob = " ".join(
            str(feed.get(k) or "") for k in ("id", "loc", "country", "region")
        ).lower()
        if needle in blob:
            hits.append(feed)
    return hits[:FEED_CAP]


def resolve_place(name: str) -> dict[str, Any] | None:
    key = (name or "").strip().lower()
    if not key:
        return None
    if key in CITIES:
        lat, lon, country = CITIES[key]
        return {"id": key, "loc": name.strip(), "lat": lat, "lon": lon, "country": country}
    for alias, coords in CITIES.items():
        if alias in key or key in alias:
            lat, lon, country = coords
            return {"id": alias, "loc": name.strip(), "lat": lat, "lon": lon, "country": country}
    return None
