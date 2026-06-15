"""TickScheduler: catch-up, last-tick guard, error capture, force_tick."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from data_simulator.clock import Clock
from data_simulator.core.pruner import Pruner
from data_simulator.core.replayer import Replayer
from data_simulator.core.scheduler import ScheduledSource, TickScheduler
from data_simulator.core.state_transitions import advance_state
from data_simulator.core.tick_plan import TickPlan
from data_simulator.state.models import SimState, SourceState
from data_simulator.state.state_store import JsonStateStore

NOW = datetime(2026, 6, 11, 9, 17, tzinfo=timezone.utc)
ALIGNED = datetime(2026, 6, 11, 9, 10, tzinfo=timezone.utc)


class FakeClock(Clock):
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakeReplayer(Replayer):
    def __init__(self, fail: bool = False, source_id: str = "fake") -> None:
        self.ticks: list[datetime] = []
        self._fail = fail
        self._source_id = source_id

    @property
    def source_id(self) -> str:
        return self._source_id

    def discover_seed(self) -> None:
        pass

    def plan_tick(self, tick: datetime, state: SourceState) -> TickPlan:
        if self._fail:
            raise RuntimeError("seed exploded")
        next_state = advance_state(state, {}, tick, ())
        return TickPlan(tick=tick, mappings=(), next_state=next_state)

    def emit(self, plan: TickPlan) -> list[Path]:
        self.ticks.append(plan.tick)
        return []


def _scheduler(tmp_path, replayer, now=NOW):
    store = JsonStateStore(tmp_path / "state.json")
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    source = ScheduledSource(
        replayer=replayer, interval_minutes=10, pruner=Pruner((out,), 180, 24)
    )
    return TickScheduler({replayer.source_id: source}, store, FakeClock(now)), store


@pytest.mark.asyncio
async def test_catch_up_emits_previous_aligned_tick(tmp_path):
    replayer = FakeReplayer()
    scheduler, store = _scheduler(tmp_path, replayer)
    await scheduler._catch_up("fake", 10)
    assert replayer.ticks == [ALIGNED]
    assert store.load().for_source("fake").last_tick == ALIGNED


@pytest.mark.asyncio
async def test_catch_up_skipped_when_tick_already_emitted(tmp_path):
    replayer = FakeReplayer()
    scheduler, store = _scheduler(tmp_path, replayer)
    store.save(SimState().with_source("fake", SourceState(last_tick=ALIGNED)))
    await scheduler._catch_up("fake", 10)
    assert replayer.ticks == []


@pytest.mark.asyncio
async def test_failed_tick_records_error_and_survives(tmp_path):
    scheduler, store = _scheduler(tmp_path, FakeReplayer(fail=True))
    await scheduler._run_tick("fake", ALIGNED)
    state = store.load().for_source("fake")
    assert state.last_error == "seed exploded"
    assert state.last_tick is None


@pytest.mark.asyncio
async def test_force_tick_runs_at_truncated_now(tmp_path):
    replayer = FakeReplayer()
    scheduler, _ = _scheduler(tmp_path, replayer)
    assert await scheduler.force_tick("fake") is True
    assert replayer.ticks == [NOW.replace(second=0, microsecond=0)]


@pytest.mark.asyncio
async def test_force_tick_unknown_source_raises(tmp_path):
    scheduler, _ = _scheduler(tmp_path, FakeReplayer())
    with pytest.raises(KeyError):
        await scheduler.force_tick("nope")
