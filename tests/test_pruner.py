"""Pruner: retention cutoff, emission-dir guard, missing files tolerated."""

from datetime import datetime, timedelta, timezone

from feed_simulator.core.pruner import Pruner
from feed_simulator.state.models import LedgerEntry, SourceState

NOW = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)


def _entry(path, age_minutes):
    return LedgerEntry(path=str(path), emitted_at=NOW - timedelta(minutes=age_minutes))


def test_old_entries_deleted_recent_kept(tmp_path):
    out = tmp_path / "glm_h5"
    out.mkdir()
    old = out / "old.nc"
    recent = out / "recent.nc"
    old.touch()
    recent.touch()

    state = SourceState(ledger=(_entry(old, 200), _entry(recent, 5)))
    pruned = Pruner((out,), retention_minutes=180).sweep(state, NOW)

    assert not old.exists()
    assert recent.exists()
    assert [e.path for e in pruned.ledger] == [str(recent)]


def test_paths_outside_emission_dirs_refused(tmp_path):
    out = tmp_path / "glm_h5"
    seed = tmp_path / "seed"
    out.mkdir()
    seed.mkdir()
    protected = seed / "seed.nc"
    protected.touch()

    state = SourceState(ledger=(_entry(protected, 999),))
    pruned = Pruner((out,), retention_minutes=180).sweep(state, NOW)

    assert protected.exists()
    assert pruned.ledger == ()


def test_missing_files_tolerated(tmp_path):
    out = tmp_path / "glm_h5"
    out.mkdir()
    state = SourceState(ledger=(_entry(out / "gone.nc", 999),))
    pruned = Pruner((out,), retention_minutes=180).sweep(state, NOW)
    assert pruned.ledger == ()


def test_non_ledger_fields_preserved(tmp_path):
    out = tmp_path / "glm_h5"
    out.mkdir()
    state = SourceState(emitted_total=7, last_error="boom", ledger=())
    pruned = Pruner((out,), retention_minutes=180).sweep(state, NOW)
    assert pruned.emitted_total == 7
    assert pruned.last_error == "boom"
