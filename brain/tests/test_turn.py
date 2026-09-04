from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.turn import collect_bus_events, run_text_turn


class FakeHermes:
    async def chat_stream(self, session_id, user_text, *, instructions):
        assert "JARVIS_PHASE1_OK" in instructions
        assert session_id == "s1"
        assert user_text == "hola"
        yield StreamEvent("assistant.delta", {"delta": "Acknowledged. "})
        yield StreamEvent("assistant.delta", {"delta": "JARVIS_PHASE1_OK."})
        yield StreamEvent("run.completed", {"ok": True})


async def test_text_turn_publishes_and_joins() -> None:
    bus = EventBus()
    seen = collect_bus_events(bus)
    cfg = BrainConfig()
    reply = await run_text_turn(
        user_text="hola",
        cfg=cfg,
        hermes=FakeHermes(),  # type: ignore[arg-type]
        bus=bus,
        session_id="s1",
    )
    assert "JARVIS_PHASE1_OK" in reply
    types = [e.type for e in seen]
    assert types[0] == "user.text"
    assert "assistant.delta" in types
    assert types[-2] == "assistant.text"
    assert seen[-1].payload["state"] == "idle"
