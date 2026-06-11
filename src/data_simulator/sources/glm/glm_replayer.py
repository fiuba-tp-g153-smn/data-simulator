"""GLM replayer: one clock-aligned window of N renamed 1-minute files per tick."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from data_simulator.core.emitter import FileEmitter
from data_simulator.core.ping_pong_cursor import PingPongCursor
from data_simulator.core.replayer import Replayer
from data_simulator.core.state_transitions import advance_state
from data_simulator.core.tick_plan import EmitMode, FileMapping, TickPlan
from data_simulator.sources.glm.glm_attr_rewriter import GlmAttrRewriter
from data_simulator.sources.glm.glm_filenames import (
    GlmFilenameParts,
    build_glm_filename,
    parse_glm_filename,
)
from data_simulator.state.models import SourceState

logger = logging.getLogger(__name__)

_CURSOR_KEY = "default"
_MINUTE = timedelta(minutes=1)


class GlmReplayer(Replayer):
    """Replays seed 1-minute GLMF files as complete aggregation windows."""

    def __init__(
        self,
        seed_dir: Path,
        dest_dir: Path,
        emitter: FileEmitter,
        attr_rewriter: GlmAttrRewriter,
        accum_minutes: int = 10,
    ) -> None:
        self._seed_dir = seed_dir
        self._dest_dir = dest_dir
        self._emitter = emitter
        self._attr_rewriter = attr_rewriter
        self._accum_minutes = accum_minutes
        self._windows: tuple[tuple[Path, ...], ...] = ()

    @property
    def source_id(self) -> str:
        return "glm"

    @property
    def window_count(self) -> int:
        return len(self._windows)

    def discover_seed(self) -> None:
        files = sorted(self._seed_dir.glob("*.nc"), key=_start_key)
        self._windows = _chunk_windows(files, self._accum_minutes)
        if not self._windows:
            raise ValueError(
                f"GLM seed at {self._seed_dir} has no complete "
                f"{self._accum_minutes}-file window"
            )
        logger.info("GLM seed: %d files -> %d windows", len(files), len(self._windows))

    def plan_tick(self, tick: datetime, state: SourceState) -> TickPlan:
        cursor = PingPongCursor(len(self._windows), state.cursors.get(_CURSOR_KEY))
        playing_backward = cursor.direction < 0
        window = self._windows[cursor.step()]
        ordered = tuple(reversed(window)) if playing_backward else window

        anchor = tick - timedelta(minutes=self._accum_minutes)
        mappings = tuple(
            self._map_file(src, anchor + i * _MINUTE) for i, src in enumerate(ordered)
        )
        next_state = advance_state(
            state,
            {_CURSOR_KEY: cursor.to_state()},
            tick,
            tuple(m.dst for m in mappings),
        )
        return TickPlan(tick=tick, mappings=mappings, next_state=next_state)

    def emit(self, plan: TickPlan) -> list[Path]:
        emitted: list[Path] = []
        for mapping in plan.mappings:
            created = self._emitter.emit_copy_with(
                mapping.src,
                mapping.dst,
                lambda part, m=mapping: self._attr_rewriter.rewrite(
                    part, m.coverage_start, m.coverage_end
                ),
            )
            if created:
                emitted.append(mapping.dst)
        return emitted

    def _map_file(self, src: Path, start: datetime) -> FileMapping:
        original = parse_glm_filename(src.name)
        end = start + _MINUTE
        new_name = build_glm_filename(
            GlmFilenameParts(
                mode=original.mode, platform=original.platform, start=start, end=end
            )
        )
        return FileMapping(
            src=src,
            dst=self._dest_dir / new_name,
            mode=EmitMode.COPY_GLM_REWRITE,
            coverage_start=start,
            coverage_end=end,
        )


def _start_key(path: Path) -> datetime:
    return parse_glm_filename(path.name).start


def _chunk_windows(files: list[Path], size: int) -> tuple[tuple[Path, ...], ...]:
    full_count = len(files) // size
    if len(files) % size:
        logger.warning("Dropping %d trailing GLM files (partial window)", len(files) % size)
    return tuple(
        tuple(files[i * size : (i + 1) * size]) for i in range(full_count)
    )


