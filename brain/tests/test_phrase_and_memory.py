from pathlib import Path

from jarvis_brain.memory.store import LocalMemory, refuse_default_mem0
from jarvis_brain.persona.overlay import choose_persona
from jarvis_brain.tools.phrase_map import match_phrase
from jarvis_brain.tools.stats import format_stats, system_stats
import pytest


def test_stats_from_proc() -> None:
    stats = system_stats()
    assert "load" in stats
    text = format_stats(stats)
    assert text.startswith("Sistema:")


def test_phrase_stats() -> None:
    hit = match_phrase("cómo está el sistema")
    assert hit is not None
    assert hit.action == "system.stats"
    assert "Sistema:" in hit.reply


def test_phrase_volume_words() -> None:
    hit = match_phrase("sube el volumen")
    assert hit is not None
    assert hit.action == "volume.up"


def test_memory_roundtrip(tmp_path: Path) -> None:
    mem = LocalMemory(tmp_path / "memory.jsonl")
    mem.add("Dario vive en Pop!_OS", role="user")
    hits = mem.search("pop")
    assert hits and "Pop" in hits[0]["text"]
    assert mem.forget(query="pop") == 1
    assert mem.search("pop") == []


def test_refuse_default_mem0() -> None:
    with pytest.raises(RuntimeError, match="PostHog"):
        refuse_default_mem0()


def test_persona_warm() -> None:
    assert choose_persona("gracias, buenos días") == "companion"
    assert choose_persona("estado del disco") == "jarvis"
