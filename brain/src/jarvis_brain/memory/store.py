from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from jarvis_brain.product.setup import product_dir


def refuse_default_mem0() -> None:
    """mem0 Memory() without config phones OpenAI + PostHog. Do not call it."""
    raise RuntimeError(
        "Memory() default is forbidden (OpenAI + PostHog). "
        "Use LocalMemory or mem0 only with Qdrant path + Ollama + MEM0_TELEMETRY=false."
    )


@dataclass
class MemoryItem:
    id: str
    text: str
    role: str
    ts: float

    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "role": self.role, "ts": self.ts}


class LocalMemory:
    """On-disk facts. Not mem0 Cloud. Not Hermes MEMORY.md."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(
            os.environ.get("JARVIS_MEMORY_FILE", product_dir() / "memory.jsonl")
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[MemoryItem]:
        if not self.path.is_file():
            return []
        items: list[MemoryItem] = []
        for raw in self.path.read_text().splitlines():
            if not raw.strip():
                continue
            data = json.loads(raw)
            items.append(
                MemoryItem(
                    id=str(data.get("id") or uuid4().hex),
                    text=str(data.get("text") or ""),
                    role=str(data.get("role") or "user"),
                    ts=float(data.get("ts") or 0),
                )
            )
        return items

    def _save(self, items: list[MemoryItem]) -> None:
        self.path.write_text("".join(json.dumps(i.to_dict()) + "\n" for i in items))
        self.path.chmod(0o600)

    def add(self, text: str, *, role: str = "user") -> MemoryItem:
        item = MemoryItem(id=uuid4().hex, text=text.strip(), role=role, ts=time.time())
        items = self._load()
        items.append(item)
        self._save(items[-400:])
        return item

    def search(self, query: str, k: int = 5) -> list[dict]:
        q = (query or "").strip().lower()
        if not q:
            return []
        scored: list[tuple[float, MemoryItem]] = []
        for item in self._load():
            hay = item.text.lower()
            if q in hay:
                score = 1.0
            else:
                words = [w for w in q.split() if len(w) > 2]
                if not words:
                    continue
                hits = sum(1 for w in words if w in hay)
                if not hits:
                    continue
                score = hits / len(words)
            scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], -pair[1].ts))
        return [
            {"id": item.id, "text": item.text, "score": score, "role": item.role}
            for score, item in scored[:k]
        ]

    def forget(self, *, query: str | None = None, id: str | None = None) -> int:
        items = self._load()
        before = len(items)
        if id:
            items = [i for i in items if i.id != id]
        elif query:
            needle = query.lower()
            items = [i for i in items if needle not in i.text.lower()]
        else:
            return 0
        self._save(items)
        return before - len(items)

    def overlay_block(self, query: str, k: int = 3) -> str:
        hits = self.search(query, k=k)
        if not hits:
            return ""
        lines = ["Known facts:"]
        for hit in hits:
            lines.append(f"- {hit['text']}")
        return "\n".join(lines)
