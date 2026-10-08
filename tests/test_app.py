import asyncio

import pytest
from fastapi.testclient import TestClient

from app.broadcaster import Broadcaster
from app.config import Settings, load_settings
from app.main import create_app, event_stream

KEY = "secret"


class FakeRequest:
    def __init__(self):
        self.disconnected = False

    async def is_disconnected(self):
        return self.disconnected


@pytest.fixture
def client():
    return TestClient(create_app(Settings(api_key=KEY, heartbeat_seconds=0.05)))


def test_health_reports_zero_clients(client):
    assert client.get("/health").json() == {"status": "ok", "clients": 0}


def test_notify_requires_key(client):
    assert client.post("/notify").status_code == 401
    assert client.post("/notify", headers={"X-API-Key": "bad"}).status_code == 401


def test_notify_with_key(client):
    r = client.post("/notify", headers={"X-API-Key": KEY})
    assert r.status_code == 200
    assert r.json() == {"status": "sent", "clients": 0}


def test_missing_api_key_setting(monkeypatch):
    monkeypatch.delenv("NOTIFY_API_KEY", raising=False)
    monkeypatch.setattr("app.config.load_dotenv", lambda: None)
    with pytest.raises(RuntimeError):
        load_settings()


def test_notify_counts_subscribers(client):
    b = client.app.state.broadcaster
    q1, q2 = b.subscribe(), b.subscribe()
    r = client.post("/notify", headers={"X-API-Key": KEY})
    assert r.json()["clients"] == 2
    assert client.get("/health").json()["clients"] == 2
    assert q1.get_nowait() == "update" and q2.get_nowait() == "update"


async def test_stream_frames_and_heartbeat():
    b = Broadcaster()
    q = b.subscribe()
    req = FakeRequest()
    gen = event_stream(req, q, 0.05)
    assert await anext(gen) == ": connected\n\n"
    assert await anext(gen) == ": heartbeat\n\n"
    b.broadcast()
    assert await anext(gen) == "event: update\ndata: changed\n\n"
    req.disconnected = True
    with pytest.raises(StopAsyncIteration):
        await anext(gen)


async def test_multiple_subscribers_each_receive():
    b = Broadcaster()
    queues = [b.subscribe() for _ in range(3)]
    assert b.broadcast() == 3
    for q in queues:
        assert q.get_nowait() == "update"


async def test_unsubscribe_and_slow_client_bounded():
    b = Broadcaster(queue_size=2)
    q = b.subscribe()
    for _ in range(10):
        b.broadcast()
    assert q.qsize() == 2
    b.unsubscribe(q)
    assert b.client_count == 0
    assert b.broadcast() == 0


async def test_cancellation_unsubscribes():
    app = create_app(Settings(api_key=KEY, heartbeat_seconds=60))
    route = next(r for r in app.routes if getattr(r, "path", "") == "/stream")
    resp = await route.endpoint(FakeRequest())
    b = app.state.broadcaster
    assert b.client_count == 1
    it = resp.body_iterator
    task = asyncio.create_task(anext(it))
    await asyncio.sleep(0.01)  # consume ": connected"
    task = asyncio.create_task(anext(it))
    await asyncio.sleep(0.01)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await it.aclose()
    assert b.client_count == 0
    assert resp.headers["x-accel-buffering"] == "no"
    assert resp.media_type == "text/event-stream"
