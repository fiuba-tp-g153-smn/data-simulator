"""Persistent simulator state: per-source cursors, last tick and emission ledger."""

from dataclasses import dataclass, field, replace
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CursorState:
    """Position of a ping-pong cursor over a seed sequence."""

    index: int = 0
    direction: int = 1


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One file emitted by the simulator, eligible for pruning later."""

    path: str
    emitted_at: datetime


@dataclass(frozen=True, slots=True)
class SourceState:
    """Replay state for a single source; cursors are keyed per seed series."""

    cursors: dict[str, CursorState] = field(default_factory=dict)
    last_tick: datetime | None = None
    emitted_total: int = 0
    last_error: str | None = None
    ledger: tuple[LedgerEntry, ...] = ()

    def with_error(self, message: str) -> "SourceState":
        return replace(self, last_error=message)


@dataclass(frozen=True, slots=True)
class SimState:
    """Top-level state for every source, persisted as a single JSON document."""

    sources: dict[str, SourceState] = field(default_factory=dict)

    def for_source(self, source_id: str) -> SourceState:
        return self.sources.get(source_id, SourceState())

    def with_source(self, source_id: str, state: SourceState) -> "SimState":
        merged = dict(self.sources)
        merged[source_id] = state
        return SimState(sources=merged)


def state_to_dict(state: SimState) -> dict:
    return {
        "sources": {
            source_id: _source_to_dict(source)
            for source_id, source in state.sources.items()
        }
    }


def state_from_dict(payload: dict) -> SimState:
    sources = {
        source_id: _source_from_dict(raw)
        for source_id, raw in payload.get("sources", {}).items()
    }
    return SimState(sources=sources)


def _source_to_dict(source: SourceState) -> dict:
    return {
        "cursors": {
            key: {"index": c.index, "direction": c.direction}
            for key, c in source.cursors.items()
        },
        "last_tick": source.last_tick.isoformat() if source.last_tick else None,
        "emitted_total": source.emitted_total,
        "last_error": source.last_error,
        "ledger": [
            {"path": entry.path, "emitted_at": entry.emitted_at.isoformat()}
            for entry in source.ledger
        ],
    }


def _source_from_dict(raw: dict) -> SourceState:
    return SourceState(
        cursors={
            key: CursorState(index=c["index"], direction=c["direction"])
            for key, c in raw.get("cursors", {}).items()
        },
        last_tick=(
            datetime.fromisoformat(raw["last_tick"]) if raw.get("last_tick") else None
        ),
        emitted_total=raw.get("emitted_total", 0),
        last_error=raw.get("last_error"),
        ledger=tuple(
            LedgerEntry(
                path=entry["path"],
                emitted_at=datetime.fromisoformat(entry["emitted_at"]),
            )
            for entry in raw.get("ledger", [])
        ),
    )
