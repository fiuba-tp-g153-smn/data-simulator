"""WRF replayer: one complete forecast run per 6-hour slot, hardlinked."""

import logging
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from feed_simulator.core.emitter import FileEmitter
from feed_simulator.core.ping_pong_cursor import PingPongCursor
from feed_simulator.core.replayer import Replayer
from feed_simulator.core.state_transitions import advance_state
from feed_simulator.core.tick_plan import EmitMode, FileMapping, TickPlan
from feed_simulator.sources.wrf.wrf_filenames import (
    build_wrf_filename,
    parse_wrf_filename,
)
from feed_simulator.sources.wrf.wrf_runs import (
    EXPECTED_FORECAST_HOURS,
    WrfRun,
    discover_complete_runs,
)
from feed_simulator.state.models import SourceState

logger = logging.getLogger(__name__)

_CURSOR_KEY = "default"


class WrfReplayer(Replayer):
    """Replays complete WRF runs with INIT_TAG rewritten to the tick slot."""

    def __init__(
        self,
        seed_dir: Path,
        dest_dir: Path,
        emitter: FileEmitter,
        expected_hours: int = EXPECTED_FORECAST_HOURS,
    ) -> None:
        self._seed_dir = seed_dir
        self._dest_dir = dest_dir
        self._emitter = emitter
        self._expected_hours = expected_hours
        self._runs: tuple[WrfRun, ...] = ()

    @property
    def source_id(self) -> str:
        return "wrf"

    @property
    def run_count(self) -> int:
        return len(self._runs)

    def discover_seed(self) -> None:
        self._runs = discover_complete_runs(self._seed_dir, self._expected_hours)
        if not self._runs:
            raise ValueError(f"WRF seed at {self._seed_dir} has no complete runs")
        logger.info(
            "WRF seed: %d complete runs (%s)",
            len(self._runs),
            ", ".join(run.init_tag for run in self._runs),
        )

    def plan_tick(self, tick: datetime, state: SourceState) -> TickPlan:
        cursor = PingPongCursor(len(self._runs), state.cursors.get(_CURSOR_KEY))
        run = self._runs[cursor.step()]
        new_tag = tick.astimezone(timezone.utc).strftime("%Y%m%d_%H0000")

        mappings = tuple(self._map_file(src, new_tag) for src in run.files)
        next_state = advance_state(
            state,
            {_CURSOR_KEY: cursor.to_state()},
            tick,
            tuple(m.dst for m in mappings),
        )
        return TickPlan(tick=tick, mappings=mappings, next_state=next_state)

    def emit(self, plan: TickPlan) -> list[Path]:
        return [
            mapping.dst
            for mapping in plan.mappings
            if self._emitter.emit_file(mapping.src, mapping.dst)
        ]

    def _map_file(self, src: Path, new_tag: str) -> FileMapping:
        parts = parse_wrf_filename(src.name)
        new_name = build_wrf_filename(replace(parts, init_tag=new_tag))
        return FileMapping(src=src, dst=self._dest_dir / new_name, mode=EmitMode.LINK)
