"""Retention sweep over the simulator's own emissions."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from data_simulator.state.models import SourceState

logger = logging.getLogger(__name__)


class Pruner:
    """Hybrid retention over the simulator's own emissions.

    An emission is kept if it falls in the newest ``retention_ticks`` ticks
    (the count-based ring) OR is younger than ``retention_minutes`` (the
    min-age floor); it is deleted only when it is both beyond the ring and
    older than the floor. The ring bounds disk and survives a stalled consumer
    (a static snapshot is never pruned out from under it); the floor guarantees
    a minimum lifetime regardless of tick rate.

    Only paths under the configured emission directories are ever unlinked —
    the seed and any file the simulator did not create are untouchable.
    """

    def __init__(
        self,
        emission_dirs: tuple[Path, ...],
        retention_minutes: int,
        retention_ticks: int,
    ) -> None:
        if retention_minutes <= 0:
            raise ValueError("retention_minutes must be > 0")
        if retention_ticks <= 0:
            raise ValueError("retention_ticks must be > 0")
        self._emission_dirs = tuple(d.resolve() for d in emission_dirs)
        self._min_age = timedelta(minutes=retention_minutes)
        self._ring_ticks = retention_ticks

    def sweep(self, state: SourceState, now: datetime) -> SourceState:
        floor_cutoff = now - self._min_age
        ticks_newest_first = sorted({e.emitted_at for e in state.ledger}, reverse=True)
        ring = set(ticks_newest_first[: self._ring_ticks])
        kept = []
        for entry in state.ledger:
            if entry.emitted_at in ring or entry.emitted_at >= floor_cutoff:
                kept.append(entry)
                continue
            self._delete(Path(entry.path))
        if len(kept) != len(state.ledger):
            logger.info(
                "Pruned %d emissions (kept newest %d ticks + younger than %s)",
                len(state.ledger) - len(kept),
                self._ring_ticks,
                self._min_age,
            )
        return SourceState(
            cursors=state.cursors,
            last_tick=state.last_tick,
            emitted_total=state.emitted_total,
            last_error=state.last_error,
            ledger=tuple(kept),
        )

    def _delete(self, path: Path) -> None:
        if not self._is_emission_path(path):
            logger.warning("Refusing to prune %s: outside emission dirs", path)
            return
        path.unlink(missing_ok=True)

    def _is_emission_path(self, path: Path) -> bool:
        resolved = path.parent.resolve() / path.name
        return any(resolved.is_relative_to(d) for d in self._emission_dirs)
