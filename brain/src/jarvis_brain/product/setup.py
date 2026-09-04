from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

from jarvis_brain.product.providers import ProviderSpec, get_provider, looks_like_key

def product_dir() -> Path:
    return Path(os.environ.get("JARVIS_HOME", Path.home() / ".config/jarvis"))


def product_file() -> Path:
    return product_dir() / "product.yaml"


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


@dataclass
class ProductConfig:
    mode: str  # demo | byok
    provider: str
    model: str
    base_url: str | None
    tts: str = "piper"
    qa: bool = False
    hermes_url: str = "http://127.0.0.1:8642"

    def to_yaml(self) -> str:
        lines = [
            f"mode: {self.mode}",
            f"provider: {self.provider}",
            f"model: {self.model}",
            f"base_url: {self.base_url or '~'}",
            f"tts: {self.tts}",
            f"qa: {'true' if self.qa else 'false'}",
            f"hermes_url: {self.hermes_url}",
        ]
        return "\n".join(lines) + "\n"


def load_product() -> ProductConfig | None:
    if not product_file().is_file():
        return None
    data: dict[str, str] = {}
    for raw in product_file().read_text().splitlines():
        if ":" not in raw or raw.strip().startswith("#"):
            continue
        k, v = raw.split(":", 1)
        data[k.strip()] = v.strip()
    base = data.get("base_url", "")
    if base in {"", "~", "null", "None"}:
        base = ""
    return ProductConfig(
        mode=data.get("mode", "demo"),
        provider=data.get("provider", "demo"),
        model=data.get("model", "mock-jarvis"),
        base_url=base or None,
        tts=data.get("tts", "piper"),
        qa=data.get("qa", "false").lower() in {"true", "1", "yes"},
        hermes_url=data.get("hermes_url", "http://127.0.0.1:8642"),
    )


def apply_setup(
    *,
    provider: str,
    api_key: str,
    model: str | None = None,
    base_url: str | None = None,
    hermes_api_key: str = "jarvis-phase1-key",
) -> ProductConfig:
    spec = get_provider(provider)
    key = (api_key or "").strip() or spec.key_hint
    if spec.id != "demo" and not looks_like_key(spec, key):
        raise ValueError(
            f"API key does not look like a {spec.id} key ({spec.key_hint})."
        )
    chosen_model = model or spec.default_model
    chosen_base = base_url or spec.default_base_url
    product = ProductConfig(
        mode="demo" if spec.id == "demo" else "byok",
        provider=spec.id,
        model=chosen_model,
        base_url=chosen_base,
        tts="piper",
        qa=spec.id == "demo",
    )
    _write_hermes(spec, key, chosen_model, chosen_base, hermes_api_key)
    dest_dir = product_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "product.yaml"
    dest.write_text(product.to_yaml())
    dest.chmod(0o600)
    return product


def _write_hermes(
    spec: ProviderSpec,
    api_key: str,
    model: str,
    base_url: str | None,
    hermes_api_key: str,
) -> None:
    home = hermes_home()
    home.mkdir(parents=True, exist_ok=True)
    env_path = home / ".env"
    cfg_path = home / "config.yaml"
    if cfg_path.is_file():
        bak = home / "config.yaml.bak"
        bak.write_text(cfg_path.read_text())
    env: dict[str, str] = {}
    if env_path.is_file():
        for raw in env_path.read_text().splitlines():
            if "=" in raw and not raw.strip().startswith("#"):
                k, v = raw.split("=", 1)
                env[k.strip()] = v.strip()
    env["API_SERVER_ENABLED"] = "true"
    env["API_SERVER_KEY"] = hermes_api_key if len(hermes_api_key) >= 16 else "jarvis-phase1-key"
    env["API_SERVER_HOST"] = env.get("API_SERVER_HOST", "127.0.0.1")
    env["API_SERVER_PORT"] = env.get("API_SERVER_PORT", "8642")
    env[spec.env_key] = api_key
    env_path.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
    env_path.chmod(0o600)

    lines = ["model:", f"  provider: {spec.hermes_provider}", f"  model: {model}"]
    if base_url:
        lines.append(f"  base_url: {base_url}")
    lines.append("  context_length: 65536")
    lines.append("  streaming: false")
    lines.append("")
    cfg_path.write_text("\n".join(lines))
    cfg_path.chmod(0o600)


def public_status(product: ProductConfig | None) -> dict:
    if product is None:
        return {"configured": False, "mode": "unset", "provider": None, "model": None}
    return {
        "configured": True,
        "mode": product.mode,
        "provider": product.provider,
        "model": product.model,
        "base_url": product.base_url,
        "tts": product.tts,
        "qa": product.qa,
        "has_key_in_env": False,  # filled by caller if needed
        **asdict(product),
    }
