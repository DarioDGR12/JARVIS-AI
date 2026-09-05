from __future__ import annotations

from urllib.parse import quote, urljoin, urlparse

import httpx
from fastapi.responses import Response

ALLOWED_SUFFIXES = (".akamaized.net",)


def host_allowed(host: str | None) -> bool:
    name = (host or "").lower()
    return any(name.endswith(suffix) for suffix in ALLOWED_SUFFIXES)


def rewrite_playlist(text: str, base: str) -> str:
    lines: list[str] = []
    root = base.rsplit("/", 1)[0] + "/"
    for line in text.splitlines():
        raw = line.strip()
        if raw and not raw.startswith("#"):
            abs_url = urljoin(root, raw)
            lines.append("/api/map/hls?u=" + quote(abs_url, safe=""))
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def fetch_hls(url: str, *, timeout_s: float = 8.0) -> Response:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not host_allowed(parsed.hostname):
        return Response("forbidden host", status_code=400)
    try:
        response = httpx.get(
            url,
            timeout=timeout_s,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://plus.nasa.gov/",
            },
        )
    except Exception as exc:
        return Response(str(exc), status_code=502)
    if response.status_code >= 400:
        return Response(response.text[:200], status_code=response.status_code)
    ctype = (response.headers.get("content-type") or "").lower()
    if "mpegurl" in ctype or url.endswith(".m3u8"):
        return Response(
            rewrite_playlist(response.text, str(response.url)),
            media_type="application/vnd.apple.mpegurl",
        )
    return Response(
        response.content,
        media_type=response.headers.get("content-type") or "application/octet-stream",
    )
