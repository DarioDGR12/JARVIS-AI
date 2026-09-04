from __future__ import annotations

from jarvis_brain.bus.envelope import Event, new_event
from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import HermesClient, HermesError


def _delta_text(event_name: str, data: dict) -> str:
    if event_name in {"assistant.delta", "message.delta"}:
        return str(
            data.get("delta")
            or data.get("text")
            or data.get("content")
            or ""
        )
    if "delta" in data and isinstance(data["delta"], str):
        return data["delta"]
    return ""


async def run_text_turn(
    *,
    user_text: str,
    cfg: BrainConfig,
    hermes: HermesClient,
    bus: EventBus,
    session_id: str,
    overlay: str | None = None,
) -> str:
    """One text turn: publish on the bus, stream Hermes, return full reply."""
    instructions = overlay if overlay is not None else cfg.overlay
    await bus.publish(
        new_event(
            "user.text",
            {"text": user_text, "session_id": session_id},
            source="cli",
        )
    )
    await bus.publish(
        new_event(
            "brain.status",
            {"state": "thinking", "session_id": session_id},
            source="brain",
        )
    )
    chunks: list[str] = []
    async for ev in hermes.chat_stream(
        session_id, user_text, instructions=instructions
    ):
        piece = _delta_text(ev.name, ev.data)
        if ev.name == "error":
            raise HermesError(str(ev.data.get("message") or ev.data))
        if piece:
            chunks.append(piece)
            await bus.publish(
                new_event(
                    "assistant.delta",
                    {"text": piece, "session_id": session_id},
                    source="brain",
                )
            )
        elif ev.name in {"assistant.completed", "run.completed", "done"}:
            final = ev.data.get("text") or ev.data.get("output") or ev.data.get(
                "content"
            )
            if isinstance(final, str) and final and not chunks:
                chunks.append(final)
    reply = "".join(chunks).strip()
    await bus.publish(
        new_event(
            "assistant.text",
            {"text": reply, "session_id": session_id},
            source="brain",
        )
    )
    await bus.publish(
        new_event(
            "brain.status",
            {"state": "idle", "session_id": session_id},
            source="brain",
        )
    )
    return reply


def collect_bus_events(bus: EventBus) -> list[Event]:
    seen: list[Event] = []

    def _keep(event: Event) -> None:
        seen.append(event)

    bus.subscribe(_keep)
    return seen
