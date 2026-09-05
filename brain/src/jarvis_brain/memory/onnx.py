from __future__ import annotations

import os


def onnx_status() -> dict[str, str | bool]:
    """Optional fastembed/ONNX. Never downloads a model from here."""
    if os.environ.get("JARVIS_MEM_ONNX") not in {"1", "true", "yes"}:
        return {"enabled": False, "reason": "flag-off"}
    try:
        import fastembed  # noqa: F401
    except ImportError:
        return {"enabled": False, "reason": "fastembed-missing"}
    return {"enabled": True, "reason": "fastembed", "backend": "fastembed"}
