from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    hermes_provider: str
    env_key: str
    default_model: str
    default_base_url: str | None
    key_hint: str


PROVIDERS: dict[str, ProviderSpec] = {
    "demo": ProviderSpec(
        id="demo",
        hermes_provider="custom",
        env_key="OPENAI_API_KEY",
        default_model="mock-jarvis",
        default_base_url="http://127.0.0.1:18765/v1",
        key_hint="sk-local",
    ),
    "openai": ProviderSpec(
        id="openai",
        hermes_provider="openai",
        env_key="OPENAI_API_KEY",
        default_model="gpt-4o-mini",
        default_base_url=None,
        key_hint="sk-...",
    ),
    "anthropic": ProviderSpec(
        id="anthropic",
        hermes_provider="anthropic",
        env_key="ANTHROPIC_API_KEY",
        default_model="claude-sonnet-4-5",
        default_base_url=None,
        key_hint="sk-ant-...",
    ),
    "openrouter": ProviderSpec(
        id="openrouter",
        hermes_provider="openrouter",
        env_key="OPENROUTER_API_KEY",
        default_model="openai/gpt-4o-mini",
        default_base_url=None,
        key_hint="sk-or-...",
    ),
    "custom": ProviderSpec(
        id="custom",
        hermes_provider="custom",
        env_key="OPENAI_API_KEY",
        default_model="local-model",
        default_base_url="http://127.0.0.1:11434/v1",
        key_hint="any (ollama often unused)",
    ),
}


def get_provider(name: str) -> ProviderSpec:
    key = name.strip().lower()
    if key not in PROVIDERS:
        known = ", ".join(sorted(PROVIDERS))
        raise ValueError(f"Unknown provider {name!r}. Use: {known}")
    return PROVIDERS[key]


def looks_like_key(provider: ProviderSpec, api_key: str) -> bool:
    raw = (api_key or "").strip()
    if provider.id == "demo":
        return len(raw) >= 4
    if provider.id == "custom":
        return bool(raw)
    if len(raw) < 8:
        return False
    if provider.id == "openai":
        return raw.startswith("sk-") and not raw.startswith("sk-ant-")
    if provider.id == "anthropic":
        return raw.startswith("sk-ant-")
    if provider.id == "openrouter":
        return raw.startswith("sk-or-")
    return len(raw) >= 8
