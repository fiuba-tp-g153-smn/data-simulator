"""JsonStateStore: roundtrip, atomicity, corrupt-file recovery."""

from datetime import datetime, timezone

from feed_simulator.state.models import (
    CursorState,
    LedgerEntry,
    SimState,
    SourceState,
)
from feed_simulator.state.state_store import JsonStateStore


def _sample_state() -> SimState:
    return SimState(
        sources={
            "glm": SourceState(
                cursors={"default": CursorState(index=3, direction=-1)},
                last_tick=datetime(2026, 6, 11, 14, 10, tzinfo=timezone.utc),
                emitted_total=30,
                last_error=None,
                ledger=(
                    LedgerEntry(
                        path="/data/glm_h5/a.nc",
                        emitted_at=datetime(2026, 6, 11, 14, 10, tzinfo=timezone.utc),
                    ),
                ),
            )
        }
    )


def test_save_load_roundtrip(tmp_path):
    store = JsonStateStore(tmp_path / "state.json")
    store.save(_sample_state())
    loaded = store.load()
    assert loaded == _sample_state()


def test_save_leaves_no_tmp_file(tmp_path):
    store = JsonStateStore(tmp_path / "state.json")
    store.save(_sample_state())
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_missing_file_returns_fresh_state(tmp_path):
    store = JsonStateStore(tmp_path / "state.json")
    assert store.load() == SimState()


def test_corrupt_file_returns_fresh_state(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{not valid json", encoding="utf-8")
    store = JsonStateStore(state_file)
    assert store.load() == SimState()


def test_for_source_and_with_source():
    state = SimState()
    assert state.for_source("radar") == SourceState()
    updated = state.with_source("radar", SourceState(emitted_total=5))
    assert updated.for_source("radar").emitted_total == 5
    assert state.sources == {}
