import json
from pathlib import Path

from fastapi.testclient import TestClient

from jarvis_brain.bus.envelope import new_event
from jarvis_brain.bus.server import EventBus
from jarvis_brain.config import BrainConfig
from jarvis_brain.hermes.client import StreamEvent
from jarvis_brain.map.feeds import FEED_CAP, filter_feeds, load_feeds, query_feeds, resolve_place
from jarvis_brain.map.state import MapState
from jarvis_brain.product.app import ProductRuntime, attach_product_routes
from jarvis_brain.product.start import repo_root
from jarvis_brain.tools.phrase_map import match_phrase
from jarvis_brain.turn import collect_bus_events, run_text_turn


class FakeHermes:
    async def ping(self):
        return {"ok": True}

    async def ensure_session(self):
        return "s-map"

    async def chat_stream(self, session_id, user_text, *, instructions):
        raise AssertionError("map phrase-map must not call Hermes")


def _client() -> TestClient:
    bus = EventBus()
    runtime = ProductRuntime(
        cfg=BrainConfig(),
        bus=bus,
        hermes=FakeHermes(),  # type: ignore[arg-type]
        tts=None,
        session_id="s-map",
    )
    return TestClient(attach_product_routes(bus.app(), runtime))


def test_feeds_are_a_short_extract() -> None:
    feeds = load_feeds()
    assert 5 <= len(feeds) <= FEED_CAP
    assert all("lat" in f and "lon" in f for f in feeds)
    raw = (repo_root() / "desktop" / "ui" / "globe" / "feeds.json").read_text()
    assert len(raw) < 20_000
    dumped = json.loads(raw)
    assert len(dumped) < 100


def test_filter_and_query() -> None:
    feeds = load_feeds()
    europe = filter_feeds(feeds, region="europe")
    assert europe and all(f["region"] == "europe" for f in europe)
    tokyo = query_feeds(feeds, "tokyo")
    assert tokyo and tokyo[0]["id"] == "tokyo"
    assert resolve_place("Tokio")["lat"] == 35.6762


def test_map_state_machine() -> None:
    world = MapState()
    world.apply(new_event("hud.show_view", {"view": "map"}, source="hud"))
    assert world.mounted is True
    world.apply(new_event("map.ready", {"source": "sentinel"}, source="sentinel"))
    assert world.ready is True
    world.apply(new_event("map.focus", {"lat": 35.67, "lon": 139.65, "zoom": 7}, source="brain"))
    assert world.last_focus["lat"] == 35.67
    world.apply(new_event("map.query", {"q": "madrid"}, source="brain"))
    assert world.visible and world.visible[0]["id"] == "madrid"
    world.apply(new_event("hud.show_view", {"view": "home"}, source="hud"))
    assert world.mounted is False
    assert world.ready is False


def test_map_api() -> None:
    client = _client()
    status = client.get("/api/status").json()
    assert status["map"]["source"] == "sentinel"
    assert status["map"]["cap"] == FEED_CAP
    listed = client.get("/api/map").json()
    assert listed["ok"] is True
    assert listed["count"] >= 5
    bad = client.post("/api/map/focus", json={"lat": "x"})
    assert bad.status_code == 400
    focused = client.post("/api/map/focus", json={"lat": 40.41, "lon": -3.70, "zoom": 6})
    assert focused.status_code == 200
    assert focused.json()["last_focus"]["lat"] == 40.41
    assert client.get("/api/hud").json()["view"] == "map"
    q = client.post("/api/map/query", json={"q": "sydney"}).json()
    assert q["hits"][0]["id"] == "sydney"
    region = client.post("/api/map/feeds", json={"region": "asia"}).json()
    assert region["feeds"] and all(f["region"] == "asia" for f in region["feeds"])


async def test_phrase_opens_map() -> None:
    bus = EventBus()
    seen = collect_bus_events(bus)
    world = MapState()
    bus.subscribe(world.apply)
    hit = match_phrase("abre el mapa")
    assert hit is not None and hit.action == "map.show"
    reply = await run_text_turn(
        user_text="dónde está Tokio",
        cfg=BrainConfig(),
        hermes=FakeHermes(),  # type: ignore[arg-type]
        bus=bus,
        session_id="s-map",
    )
    assert "Tokio" in reply or "tok" in reply.lower()
    types = [e.type for e in seen]
    assert "hud.show_view" in types
    assert "map.focus" in types
    assert world.last_focus["lat"] == 35.6762
