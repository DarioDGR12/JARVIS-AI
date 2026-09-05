from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from jarvis_brain.memory.store import refuse_default_mem0
from jarvis_brain.product.setup import product_dir


def mem0_root() -> Path:
    return Path(os.environ.get("JARVIS_MEM0_PATH", product_dir() / "mem0"))


def ollama_base() -> str:
    return (
        os.environ.get("JARVIS_OLLAMA_URL")
        or os.environ.get("OLLAMA_HOST")
        or "http://127.0.0.1:11434"
    ).rstrip("/")


def ollama_up(timeout_s: float = 0.6) -> bool:
    try:
        r = httpx.get(f"{ollama_base()}/api/tags", timeout=timeout_s)
        return r.status_code < 400
    except Exception:
        return False


def local_mem0_config(root: Path | None = None) -> dict[str, Any]:
    """Explicit local backends. Never the Memory() OpenAI+PostHog default."""
    dest = root or mem0_root()
    dest.mkdir(parents=True, exist_ok=True)
    host = ollama_base()
    dims = int(os.environ.get("JARVIS_MEM0_DIMS", "768"))
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "jarvis",
                "path": str(dest / "qdrant"),
                "on_disk": True,
                "embedding_model_dims": dims,
            },
        },
        "llm": {
            "provider": "ollama",
            "config": {
                "model": os.environ.get("JARVIS_MEM0_LLM", "llama3.1:8b"),
                "ollama_base_url": host,
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": os.environ.get("JARVIS_MEM0_EMBED", "nomic-embed-text"),
                "ollama_base_url": host,
                "embedding_dims": dims,
            },
        },
    }


class Mem0Local:
    """mem0 OSS. Telemetry forced off. Memory() without config is forbidden."""

    def __init__(self, client: Any, *, user_id: str = "dario") -> None:
        self._m = client
        self.user_id = user_id

    @classmethod
    def maybe(cls, *, user_id: str = "dario") -> Mem0Local | None:
        os.environ["MEM0_TELEMETRY"] = "false"
        if os.environ.get("JARVIS_MEM0", "1") in {"0", "false", "no"}:
            return None
        if not ollama_up():
            return None
        try:
            from mem0 import Memory  # type: ignore
        except Exception:
            return None
        try:
            client = Memory.from_config(local_mem0_config())
        except Exception:
            return None
        return cls(client, user_id=user_id)

    def add(self, text: str) -> None:
        os.environ["MEM0_TELEMETRY"] = "false"
        self._m.add(text, user_id=self.user_id)

    def search(self, query: str, k: int = 5) -> list[dict]:
        os.environ["MEM0_TELEMETRY"] = "false"
        raw = self._m.search(query, user_id=self.user_id, limit=k)
        items = raw.get("results", raw) if isinstance(raw, dict) else raw
        out: list[dict] = []
        for item in items or []:
            if isinstance(item, dict):
                text = str(item.get("memory") or item.get("text") or "")
                if text:
                    out.append(
                        {
                            "id": str(item.get("id") or ""),
                            "text": text,
                            "score": float(item.get("score") or 0),
                            "role": "fact",
                        }
                    )
        return out[:k]

    def forget(self, *, query: str | None = None, id: str | None = None) -> int:
        os.environ["MEM0_TELEMETRY"] = "false"
        if id:
            try:
                self._m.delete(memory_id=id)
                return 1
            except Exception:
                return 0
        if not query:
            return 0
        removed = 0
        for hit in self.search(query, k=8):
            hid = hit.get("id")
            if not hid:
                continue
            try:
                self._m.delete(memory_id=hid)
                removed += 1
            except Exception:
                continue
        return removed


def open_default_mem0() -> None:
    refuse_default_mem0()
