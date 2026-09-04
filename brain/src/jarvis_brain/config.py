from __future__ import annotations

import os
from dataclasses import dataclass

PERSONALITY_OVERLAY = (
    "You are JARVIS, a personal assistant. Tone: dry, neutral, functional. "
    "Answer in 1-3 sentences. Do not mention being an LLM. "
    "Reply in the user's language."
)
QA_OVERLAY_SUFFIX = (
    " If this overlay reached you, include the exact token JARVIS_PHASE1_OK "
    "once in your reply."
)


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def build_overlay(*, qa: bool | None = None) -> str:
    base = os.environ.get("JARVIS_OVERLAY", PERSONALITY_OVERLAY).strip()
    use_qa = _truthy("JARVIS_QA") if qa is None else qa
    if use_qa and "JARVIS_PHASE1_OK" not in base:
        return f"{base}{QA_OVERLAY_SUFFIX}"
    return base


@dataclass(frozen=True)
class BrainConfig:
    bus_host: str = "0.0.0.0"
    bus_port: int = 8765
    hermes_base_url: str = "http://127.0.0.1:8642"
    # Hermes refuses to start the API server if the key is < 16 chars.
    hermes_api_key: str = "jarvis-phase1-key"
    hermes_session_name: str = "jarvis-main"
    hermes_session_key: str = "jarvis:user:main"
    hermes_timeout_s: float = 120.0
    overlay: str = PERSONALITY_OVERLAY

    @classmethod
    def from_env(cls) -> BrainConfig:
        port = int(os.environ.get("PORT") or os.environ.get("JARVIS_BUS_PORT") or "8765")
        return cls(
            bus_host=os.environ.get("JARVIS_BUS_HOST", "0.0.0.0"),
            bus_port=port,
            hermes_base_url=os.environ.get(
                "JARVIS_HERMES_URL", "http://127.0.0.1:8642"
            ).rstrip("/"),
            hermes_api_key=os.environ.get("API_SERVER_KEY")
            or os.environ.get("JARVIS_HERMES_KEY")
            or "jarvis-phase1-key",
            hermes_session_name=os.environ.get("JARVIS_SESSION", "jarvis-main"),
            hermes_session_key=os.environ.get(
                "JARVIS_SESSION_KEY", "jarvis:user:main"
            ),
            hermes_timeout_s=float(os.environ.get("JARVIS_HERMES_TIMEOUT", "120")),
            overlay=build_overlay(),
        )
