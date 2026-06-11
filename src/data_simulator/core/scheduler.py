"""Asyncio scheduler: clock-aligned ticks per source with catch-up on start."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from data_simulator.clock import Clock
from data_simulator.core.pruner import Pruner
from data_simulator.core.replayer import Replayer
from data_simulator.core.tick_alignment import next_aligned, prev_aligned
from data_simulator.state.state_store import JsonStateStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScheduledSource:
    """One replayer wired to its cadence and retention."""

    replayer: Replayer
    interval_minutes: int
    pruner: Pruner


class TickScheduler:
    """Runs every enabled source on its aligned cadence and persists state."""

    def __init__(
        self,
        sources: dict[str, ScheduledSource],
        state_store: JsonStateStore,
        clock: Clock,
    ) -> None:
        self._sources = sources
        self._state_store = state_store
        self._clock = clock
        self._locks = {source_id: asyncio.Lock() for source_id in sources}
        self._tasks: list[asyncio.Task] = []

    @property
    def source_ids(self) -> list[str]:
        return sorted(self._sources)

    def interval_minutes(self, source_id: str) -> int:
        return self._sources[source_id].interval_minutes

    def start(self) -> None:
        for source_id in self._sources:
            self._tasks.append(asyncio.create_task(self._run_loop(source_id)))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def force_tick(self, source_id: str) -> bool:
        """Run a tick now (truncated to the minute). False if one is running."""
        if source_id not in self._sources:
            raise KeyError(source_id)
        lock = self._locks[source_id]
        if lock.locked():
            return False
        tick = self._clock.now().replace(second=0, microsecond=0)
        await self._run_tick(source_id, tick)
        return True

    async def _run_loop(self, source_id: str) -> None:
        interval = self._sources[source_id].interval_minutes
        await self._catch_up(source_id, interval)
        while True:
            target = next_aligned(self._clock.now(), interval)
            await asyncio.sleep(max((target - self._clock.now()).total_seconds(), 0))
            await self._run_tick(source_id, target)

    async def _catch_up(self, source_id: str, interval: int) -> None:
        tick = prev_aligned(self._clock.now(), interval)
        state = self._state_store.load().for_source(source_id)
        if state.last_tick is not None and state.last_tick >= tick:
            logger.info("[%s] Tick %s already emitted; skipping catch-up", source_id, tick)
            return
        await self._run_tick(source_id, tick)

    async def _run_tick(self, source_id: str, tick: datetime) -> None:
        source = self._sources[source_id]
        async with self._locks[source_id]:
            try:
                await self._plan_emit_persist(source_id, source, tick)
            except Exception as exc:  # noqa: BLE001 — loop must survive any tick failure
                logger.exception("[%s] Tick %s failed", source_id, tick)
                self._record_error(source_id, exc)

    async def _plan_emit_persist(
        self, source_id: str, source: ScheduledSource, tick: datetime
    ) -> None:
        state = self._state_store.load().for_source(source_id)
        plan = source.replayer.plan_tick(tick, state)
        emitted = await asyncio.to_thread(source.replayer.emit, plan)
        logger.info("[%s] Tick %s emitted %d files", source_id, tick, len(emitted))
        pruned = source.pruner.sweep(plan.next_state, self._clock.now())
        self._persist(source_id, pruned)

    def _record_error(self, source_id: str, exc: Exception) -> None:
        state = self._state_store.load().for_source(source_id)
        self._persist(source_id, state.with_error(str(exc)))

    def _persist(self, source_id: str, state) -> None:
        sim_state = self._state_store.load()
        self._state_store.save(sim_state.with_source(source_id, state))
