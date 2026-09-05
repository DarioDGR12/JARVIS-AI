from __future__ import annotations

from jarvis_brain.memory.lexical import rank_texts
from jarvis_brain.memory.mem0_local import Mem0Local
from jarvis_brain.memory.store import LocalMemory, MemoryItem


class LayeredMemory:
    """JSONL first. Lexical rank always. mem0 only when Qdrant+Ollama are up."""

    def __init__(self, local: LocalMemory, remote: Mem0Local | None = None) -> None:
        self.local = local
        self.remote = remote
        self.path = local.path

    @property
    def backend(self) -> str:
        if self.remote:
            return "mem0+jsonl"
        return "jsonl+lexical"

    def add(self, text: str, *, role: str = "user") -> MemoryItem:
        item = self.local.add(text, role=role)
        if role == "fact" and self.remote is not None:
            try:
                self.remote.add(text)
            except Exception:
                pass
        return item

    def search(self, query: str, k: int = 5) -> list[dict]:
        pool = list(self.local.list_facts(k=80))
        hits = rank_texts(query, pool, k=k)
        seen = {str(h.get("text") or "") for h in hits}
        if not hits:
            hits = list(self.local.search(query, k=k))
            seen = {str(h.get("text") or "") for h in hits}
        if self.remote is not None:
            try:
                for extra in self.remote.search(query, k=k):
                    if extra.get("text") in seen:
                        continue
                    hits.append(extra)
                    seen.add(str(extra.get("text") or ""))
            except Exception:
                pass
        return hits[:k]

    def list_facts(self, k: int = 20) -> list[dict]:
        return self.local.list_facts(k=k)

    def forget(self, *, query: str | None = None, id: str | None = None) -> int:
        removed = self.local.forget(query=query, id=id)
        if self.remote is not None:
            try:
                removed += self.remote.forget(query=query, id=id)
            except Exception:
                pass
        return removed

    def overlay_block(self, query: str, k: int = 3) -> str:
        hits = self.search(query, k=k)
        if not hits:
            return ""
        lines = ["Known facts:"]
        for hit in hits:
            lines.append(f"- {hit['text']}")
        return "\n".join(lines)
