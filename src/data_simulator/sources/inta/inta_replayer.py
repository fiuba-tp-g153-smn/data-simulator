"""INTA replayer: one 240 km volume and one long-range PPI per station per tick."""

import logging
from datetime import datetime
from pathlib import Path

from data_simulator.core.emitter import FileEmitter
from data_simulator.core.ping_pong_cursor import PingPongCursor
from data_simulator.core.replayer import Replayer
from data_simulator.core.state_transitions import advance_state
from data_simulator.core.tick_plan import EmitMode, FileMapping, TickPlan
from data_simulator.sources.inta.inta_filenames import (
    build_inta_filename,
    parse_inta_filename,
)
from data_simulator.sources.inta.inta_grouping import (
    IntaScan,
    group_inta_seed,
    is_long_range_series,
    station_of,
)
from data_simulator.state.models import CursorState, SourceState

logger = logging.getLogger(__name__)


class IntaReplayer(Replayer):
    """Replays INTA Rainbow5 files with the filename timestamp set to the tick.

    tiles-processor takes the scan time from the filename and the station from
    the header, so renaming is enough; the file content is never touched. The
    .vol volumes and the .azi long-range PPIs of a station are separate series
    with their own cursors, both emitted at the tick: they feed different
    products (dbzh vs dbzh-450km), so the shared timestamp never collides.
    """

    def __init__(self, seed_dir: Path, dest_dir: Path, emitter: FileEmitter) -> None:
        self._seed_dir = seed_dir
        self._dest_dir = dest_dir
        self._emitter = emitter
        self._series: dict[str, tuple[IntaScan, ...]] = {}

    @property
    def source_id(self) -> str:
        return "inta"

    @property
    def group_count(self) -> int:
        return len(self._series)

    def discover_seed(self) -> None:
        files = [
            path
            for pattern in ("*.vol", "*/*.vol", "*.azi", "*/*.azi")
            for path in self._seed_dir.glob(pattern, case_sensitive=False)
        ]
        self._series = group_inta_seed(files, self._seed_dir)
        if not any(not is_long_range_series(key) for key in self._series):
            raise ValueError(
                f"INTA seed at {self._seed_dir} has no parsable 240 km .vol scans"
            )
        if not any(is_long_range_series(key) for key in self._series):
            logger.warning(
                "INTA seed at %s has no long-range .azi scans; dbzh-450km will "
                "not be replayed",
                self._seed_dir,
            )
        logger.info("INTA seed: %d files -> %d series", len(files), len(self._series))

    def plan_tick(self, tick: datetime, state: SourceState) -> TickPlan:
        mappings: list[FileMapping] = []
        cursors: dict[str, CursorState] = {}
        for key in sorted(self._series):
            scans = self._series[key]
            cursor = PingPongCursor(len(scans), state.cursors.get(key))
            scan = scans[cursor.step()]
            cursors[key] = cursor.to_state()
            mappings.extend(self._map_scan(station_of(key), scan, tick))
        next_state = advance_state(
            state, cursors, tick, tuple(m.dst for m in mappings)
        )
        return TickPlan(tick=tick, mappings=tuple(mappings), next_state=next_state)

    def emit(self, plan: TickPlan) -> list[Path]:
        return [
            mapping.dst
            for mapping in plan.mappings
            if self._emitter.emit_file(mapping.src, mapping.dst)
        ]

    def _map_scan(
        self, station: str, scan: IntaScan, tick: datetime
    ) -> list[FileMapping]:
        return [
            FileMapping(
                src=src,
                dst=self._dest_dir
                / station
                / build_inta_filename(parse_inta_filename(src.name).with_timestamp(tick)),
                mode=EmitMode.LINK,
            )
            for src in scan.files
        ]
