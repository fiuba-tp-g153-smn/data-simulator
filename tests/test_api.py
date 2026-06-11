"""HTTP API: health, status payload, force tick, unknown source."""

from pathlib import Path

from fastapi.testclient import TestClient

from feed_simulator.api.app import create_app
from feed_simulator.config import Settings
from tests.test_scheduler import NOW, FakeClock, FakeReplayer, _scheduler


def _client(tmp_path: Path):
    replayer = FakeReplayer(source_id="glm")
    scheduler, store = _scheduler(tmp_path, replayer)
    settings = Settings.from_env(env={"SIM_DATA_ROOT": str(tmp_path)})
    app = create_app(scheduler, store, settings, FakeClock(NOW))
    return TestClient(app), replayer


def test_health(tmp_path):
    client, _ = _client(tmp_path)
    assert client.get("/health").json() == {"status": "ok"}


def test_status_reports_source(tmp_path):
    client, _ = _client(tmp_path)
    client.post("/tick/glm")
    payload = client.get("/status").json()
    source = payload["sources"]["glm"]
    assert source["interval_minutes"] == 10
    assert source["retention_minutes"] == 180
    assert source["last_tick"] is not None
    assert source["next_tick"] == "2026-06-11T09:20:00Z"
    assert source["last_error"] is None


def test_force_tick_triggers_emission(tmp_path):
    client, replayer = _client(tmp_path)
    response = client.post("/tick/glm")
    assert response.status_code == 200
    assert response.json() == {"source": "glm", "triggered": True}
    assert len(replayer.ticks) == 1


def test_tick_unknown_source_404(tmp_path):
    client, _ = _client(tmp_path)
    assert client.post("/tick/nope").status_code == 404
