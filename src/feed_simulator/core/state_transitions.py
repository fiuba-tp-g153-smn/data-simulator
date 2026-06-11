"""Shared pure state transition applied after planning a tick."""

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from feed_simulator.state.models import CursorState, LedgerEntry, SourceState


def advance_state(
    state: SourceState,
    cursors: dict[str, CursorState],
    tick: datetime,
    dests: tuple[Path, ...],
) -> SourceState:
    """Fold a planned tick into the source state (cursors, ledger, counters)."""
    merged_cursors = dict(state.cursors)
    merged_cursors.update(cursors)
    ledger = state.ledger + tuple(
        LedgerEntry(path=str(dst), emitted_at=tick) for dst in dests
    )
    return replace(
        state,
        cursors=merged_cursors,
        last_tick=tick,
        emitted_total=state.emitted_total + len(dests),
        last_error=None,
        ledger=ledger,
    )
