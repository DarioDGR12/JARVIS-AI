from jarvis_brain.bus.envelope import Event, new_event


def test_roundtrip() -> None:
    ev = new_event("user.text", {"text": "hi"}, source="cli")
    again = Event.from_dict(ev.to_dict())
    assert again.type == "user.text"
    assert again.payload["text"] == "hi"
    assert again.source == "cli"
    assert again.v == 1


def test_from_dict_requires_type() -> None:
    try:
        Event.from_dict({"payload": {}})
    except ValueError:
        return
    raise AssertionError("expected ValueError")
