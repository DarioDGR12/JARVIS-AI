from __future__ import annotations

import re


_WORD = re.compile(r"[a-z0-9áéíóúüñ]{2,}", re.I)


def tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORD.finditer(text or "")}


def char_grams(text: str, n: int = 3) -> set[str]:
    compact = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if len(compact) < n:
        return {compact} if compact else set()
    return {compact[i : i + n] for i in range(len(compact) - n + 1)}


def lexical_score(query: str, text: str) -> float:
    """Local ranking. No embeddings, no Ollama, no Memory()."""
    q = (query or "").strip()
    hay = text or ""
    if not q or not hay:
        return 0.0
    ql, hl = q.lower(), hay.lower()
    if ql in hl:
        return 1.0
    qw, tw = tokens(q), tokens(hay)
    word = (len(qw & tw) / len(qw)) if qw else 0.0
    qg, tg = char_grams(q), char_grams(hay)
    gram = (len(qg & tg) / len(qg | tg)) if qg and tg else 0.0
    return max(word, gram * 0.9)


def rank_texts(query: str, items: list[dict], *, k: int = 5) -> list[dict]:
    scored: list[tuple[float, dict]] = []
    for item in items:
        score = lexical_score(query, str(item.get("text") or ""))
        if score <= 0:
            continue
        row = dict(item)
        row["score"] = round(score, 4)
        scored.append((score, row))
    scored.sort(key=lambda pair: -pair[0])
    return [row for _, row in scored[:k]]
