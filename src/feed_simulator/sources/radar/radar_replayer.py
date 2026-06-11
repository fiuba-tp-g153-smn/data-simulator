"""Radar replayer: one scan per (radar, subvolume) series per tick, hardlinked."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from feed_simulator.core.emitter import FileEmitter
from feed_simulator.core.ping_pong_cursor import PingPongCursor
from feed_simulator.core.replayer import Replayer
from feed_simulator.core.state_transitions import advance_state
from feed_simulator.core.tick_plan import EmitMode, FileMapping, TickPlan
from feed_simulator.sources.radar.radar_filenames import (
    build_radar_filename,
    parse_radar_filename,
)
from feed_simulator.sources.radar.radar_grouping import RadarScan, group_radar_seed
from feed_simulator.state.models import CursorState, SourceState

logger = logging.getLogger(__name__)

# Distinct per-subvolume offsets keep image_ids unique for variables present in
# more than one subvolume (e.g. DBZH lives in both 01 and 04).
_SUBVOLUME_OFFSETS = {"01": 0, "02": 20, "04": 40}
_FALLBACK_OFFSET = 50


class RadarReplayer(Replayer):
    """Replays per-radar volume scans with timestamps rewritten to the tick."""

    def __init__(self, seed_dir: Path, dest_dir: Path, emitter: FileEmitter) -> None:
        self._seed_dir = seed_dir
        self._dest_dir = dest_dir
        self._emitter = emitter
        self._series: dict[str, tuple[RadarScan, ...]] = {}

    @property
    def source_id(self) -> str:
        return "radar"

    @property
    def group_count(self) -> int:
        return len(self._series)

    def discover_seed(self) -> None:
        files = [
            path
            for pattern in ("*.H5", "*.h5", "*/*.H5", "*/*.h5")
            for path in self._seed_dir.glob(pattern)
        ]
        self._series = group_radar_seed(files)
        if not self._series:
            raise ValueError(f"Radar seed at {self._seed_dir} has no parsable H5 files")
        logger.info(
            "Radar seed: %d files -> %d (radar, subvolume) series",
            len(files),
            len(self._series),
        )

    def plan_tick(self, tick: datetime, state: SourceState) -> TickPlan:
        mappings: list[FileMapping] = []
        cursors: dict[str, CursorState] = {}
        for key in sorted(self._series):
            scans = self._series[key]
            cursor = PingPongCursor(len(scans), state.cursors.get(key))
            scan = scans[cursor.step()]
            cursors[key] = cursor.to_state()
            mappings.extend(self._map_scan(scan, tick))
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

    def _map_scan(self, scan: RadarScan, tick: datetime) -> list[FileMapping]:
        mappings = []
        for src in scan.files:
            parts = parse_radar_filename(src.name)
            new_ts = tick + timedelta(seconds=_subvolume_offset(parts.subvolume))
            new_name = build_radar_filename(parts.with_timestamp(new_ts))
            mappings.append(
                FileMapping(
                    src=src,
                    dst=self._dest_dir / parts.radar_id / new_name,
                    mode=EmitMode.LINK,
                )
            )
        return mappings


def _subvolume_offset(subvolume: str) -> int:
    offset = _SUBVOLUME_OFFSETS.get(subvolume)
    if offset is None:
        logger.warning("Unknown subvolume %s; using fallback offset", subvolume)
        return _FALLBACK_OFFSET
    return offset
