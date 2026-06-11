"""Retention sweep over the simulator's own emissions."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from feed_simulator.state.models import SourceState

logger = logging.getLogger(__name__)


class Pruner:
    """Deletes ledgered emissions older than the retention window.

    Only paths under the configured emission directories are ever unlinked —
    the seed and any file the simulator did not create are untouchable.
    """

    def __init__(self, emission_dirs: tuple[Path, ...], retention_minutes: int) -> None:
        if retention_minutes <= 0:
            raise ValueError("retention_minutes must be > 0")
        self._emission_dirs = tuple(d.resolve() for d in emission_dirs)
        self._retention = timedelta(minutes=retention_minutes)

    def sweep(self, state: SourceState, now: datetime) -> SourceState:
        cutoff = now - self._retention
        kept = []
        for entry in state.ledger:
            if entry.emitted_at >= cutoff:
                kept.append(entry)
                continue
            self._delete(Path(entry.path))
        if len(kept) != len(state.ledger):
            logger.info("Pruned %d emissions", len(state.ledger) - len(kept))
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
