from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def ocr_image(path: Path) -> str:
    """Local Tesseract if installed. Never call a cloud VLM from here."""
    bin_path = shutil.which("tesseract")
    if not bin_path:
        return ""
    try:
        proc = subprocess.run(
            [bin_path, str(path), "stdout", "-l", "spa+eng", "--psm", "6"],
            capture_output=True,
            timeout=8,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (proc.stdout or "").strip()[:2000]
