import importlib.util
from pathlib import Path


def _load_mock():
    path = Path(__file__).resolve().parents[1] / "scripts" / "mock_openai_llm.py"
    spec = importlib.util.spec_from_file_location("mock_openai_llm", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_overlay_hit_echoes_marker() -> None:
    mock = _load_mock()
    text, hit, system, user = mock.reply_for_messages(
        [
            {"role": "system", "content": "You are JARVIS. JARVIS_PHASE1_OK"},
            {"role": "user", "content": "hola"},
        ]
    )
    assert hit is True
    assert "JARVIS_PHASE1_OK" in text
    assert "hola" in text
    assert "JARVIS_PHASE1_OK" in system
    assert user == "hola"


def test_missing_overlay() -> None:
    mock = _load_mock()
    text, hit, _, _ = mock.reply_for_messages(
        [{"role": "system", "content": "plain"}, {"role": "user", "content": "x"}]
    )
    assert hit is False
    assert "JARVIS_PHASE1_OK" not in text
