from __future__ import annotations

from typing import Any, Callable

import httpx

from jarvis_brain.map.feeds import resolve_place

# WMO Weather interpretation codes → Spanish, short.
_WMO = {
    0: "despejado",
    1: "mayormente despejado",
    2: "parcialmente nublado",
    3: "nublado",
    45: "niebla",
    48: "niebla con escarcha",
    51: "llovizna débil",
    53: "llovizna",
    55: "llovizna fuerte",
    61: "lluvia débil",
    63: "lluvia",
    65: "lluvia fuerte",
    71: "nieve débil",
    73: "nieve",
    75: "nieve fuerte",
    80: "chubascos",
    81: "chubascos",
    82: "chubascos fuertes",
    95: "tormenta",
    96: "tormenta con granizo",
    99: "tormenta con granizo",
}

WeatherFetch = Callable[[float, float], str | None]


def describe_code(code: int | None) -> str:
    if code is None:
        return "sin código"
    return _WMO.get(int(code), f"código {int(code)}")


def format_current(payload: dict[str, Any], *, lat: float, lon: float) -> str | None:
    current = payload.get("current") or {}
    temp = current.get("temperature_2m")
    code = current.get("weather_code")
    if temp is None and code is None:
        return None
    sky = describe_code(int(code) if code is not None else None)
    if temp is None:
        return f"Clima {lat:.2f},{lon:.2f}: {sky}."
    return f"Clima {lat:.2f},{lon:.2f}: {float(temp):.0f} °C, {sky}."


def fetch_weather(lat: float, lon: float, *, timeout_s: float = 2.5) -> str | None:
    """Open-Meteo, no API key. Offline → None."""
    try:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code",
                "timezone": "auto",
            },
            timeout=timeout_s,
        )
        if response.status_code >= 400:
            return None
        return format_current(response.json(), lat=lat, lon=lon)
    except Exception:
        return None


def attach_weather(
    text: str,
    q: str,
    *,
    fetch: WeatherFetch | None = fetch_weather,
) -> str:
    """Append one Open-Meteo line when the briefing has a place. Fail soft."""
    if not fetch:
        return text
    place = resolve_place(q) if q else None
    if not place:
        return text
    try:
        line = fetch(float(place["lat"]), float(place["lon"]))
    except Exception:
        return text
    if not line:
        return text
    return f"{text.rstrip()}\n{line}"
