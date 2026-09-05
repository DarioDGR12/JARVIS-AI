from __future__ import annotations

import re
import shutil
import subprocess
from urllib.parse import urlparse

_URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.I)


def extract_urls(text: str, *, limit: int = 8) -> list[str]:
    """http(s) only. file:// and javascript: stay out."""
    found: list[str] = []
    for match in _URL_RE.finditer(text or ""):
        raw = match.group(0).rstrip(".,);]>\"'")
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if raw not in found:
            found.append(raw)
        if len(found) >= limit:
            break
    return found


def open_urls(urls: list[str], *, opener: str | None = None) -> list[str]:
    """xdg-open each http(s) URL. Returns the ones we launched."""
    bin_path = opener or shutil.which("xdg-open")
    if not bin_path:
        return []
    opened: list[str] = []
    for url in extract_urls(" ".join(urls) if urls else ""):
        try:
            subprocess.Popen(
                [bin_path, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            opened.append(url)
        except OSError:
            continue
    return opened
