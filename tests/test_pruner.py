"""Pruner: hybrid ring + min-age floor, emission-dir guard, missing files tolerated."""

from datetime import datetime, timedelta, timezone

from data_simulator.core.pruner import Pruner
from data_simulator.state.models import LedgerEntry, SourceState

NOW = datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)


def _entry(path, age_minutes):
    return LedgerEntry(path=str(path), emitted_at=NOW - timedelta(minutes=age_minutes))


def _touch(dir_path, name):
    dir_path.mkdir(parents=True, exist_ok=True)
    f = dir_path / name
    f.touch()
    return f


def test_entry_beyond_ring_and_older_than_floor_is_deleted(tmp_path):
    out = tmp_path / "goes19-glm"
    old = _touch(out, "old.nc")
    recent = _touch(out, "recent.nc")

    # ring=1 keeps only the newest tick (recent); old is beyond the ring AND
    # older than the 180-min floor, so it is deleted.
    state = SourceState(ledger=(_entry(old, 200), _entry(recent, 5)))
    pruned = Pruner((out,), retention_minutes=180, retention_ticks=1).sweep(state, NOW)

    assert not old.exists()
    assert recent.exists()
    assert [e.path for e in pruned.ledger] == [str(recent)]


def test_ring_evicts_oldest_ticks_beyond_n(tmp_path):
    out = tmp_path / "goes19-glm"
    # Five distinct ticks, all older than the floor so only the ring decides.
    ages = [200, 250, 300, 400, 500]
    files = {age: _touch(out, f"f{age}.nc") for age in ages}
    state = SourceState(ledger=tuple(_entry(files[age], age) for age in ages))

    pruned = Pruner((out,), retention_minutes=180, retention_ticks=3).sweep(state, NOW)

    # Newest 3 ticks (200, 250, 300) survive; the 2 oldest are evicted.
    for age in (200, 250, 300):
        assert files[age].exists()
    for age in (400, 500):
        assert not files[age].exists()
    assert len(pruned.ledger) == 3


def test_floor_protects_young_entries_beyond_ring(tmp_path):
    out = tmp_path / "goes19-glm"
    # Three young ticks (all < 180-min floor) but a ring of only 2: the 3rd-newest
    # is beyond the ring yet protected by the floor, so nothing is deleted.
    ages = [10, 20, 30]
    files = {age: _touch(out, f"f{age}.nc") for age in ages}
    state = SourceState(ledger=tuple(_entry(files[age], age) for age in ages))

    pruned = Pruner((out,), retention_minutes=180, retention_ticks=2).sweep(state, NOW)

    for age in ages:
        assert files[age].exists()
    assert len(pruned.ledger) == 3


def test_delete_requires_both_beyond_ring_and_older_than_floor(tmp_path):
    out = tmp_path / "goes19-glm"
    young_ring = _touch(out, "young_ring.nc")  # newest tick → in the ring
    young_floor = _touch(out, "young_floor.nc")  # beyond ring, but within floor
    old = _touch(out, "old.nc")  # beyond ring AND older than floor
    state = SourceState(
        ledger=(
            _entry(young_ring, 5),
            _entry(young_floor, 30),
            _entry(old, 300),
        )
    )

    pruned = Pruner((out,), retention_minutes=180, retention_ticks=1).sweep(state, NOW)

    assert young_ring.exists()
    assert young_floor.exists()  # floor protected it despite being beyond the ring
    assert not old.exists()  # only the entry failing BOTH guards is deleted
    assert {e.path for e in pruned.ledger} == {str(young_ring), str(young_floor)}


def test_fewer_ticks_than_ring_size_keeps_all(tmp_path):
    out = tmp_path / "goes19-glm"
    ages = [200, 400]  # older than floor, but only 2 ticks vs a ring of 5
    files = {age: _touch(out, f"f{age}.nc") for age in ages}
    state = SourceState(ledger=tuple(_entry(files[age], age) for age in ages))

    pruned = Pruner((out,), retention_minutes=180, retention_ticks=5).sweep(state, NOW)

    for age in ages:
        assert files[age].exists()
    assert len(pruned.ledger) == 2


def test_paths_outside_emission_dirs_refused(tmp_path):
    out = tmp_path / "goes19-glm"
    seed = tmp_path / "seed"
    out.mkdir()
    seed.mkdir()
    protected = seed / "seed.nc"
    protected.touch()
    recent = _touch(out, "recent.nc")  # newer tick fills the ring

    # protected is beyond the ring (1) and older than the floor, so it is
    # SELECTED for deletion — but it lives outside the emission dir, so the
    # guard refuses to unlink it while still dropping it from the ledger.
    state = SourceState(ledger=(_entry(protected, 999), _entry(recent, 5)))
    pruned = Pruner((out,), retention_minutes=180, retention_ticks=1).sweep(state, NOW)

    assert protected.exists()
    assert recent.exists()
    assert [e.path for e in pruned.ledger] == [str(recent)]


def test_missing_files_tolerated(tmp_path):
    out = tmp_path / "goes19-glm"
    recent = _touch(out, "recent.nc")
    # gone.nc is selected for deletion (beyond ring + older than floor) but never
    # existed on disk — unlink(missing_ok=True) tolerates it.
    state = SourceState(ledger=(_entry(out / "gone.nc", 999), _entry(recent, 5)))
    pruned = Pruner((out,), retention_minutes=180, retention_ticks=1).sweep(state, NOW)

    assert recent.exists()
    assert [e.path for e in pruned.ledger] == [str(recent)]


def test_non_ledger_fields_preserved(tmp_path):
    out = tmp_path / "goes19-glm"
    out.mkdir()
    state = SourceState(emitted_total=7, last_error="boom", ledger=())
    pruned = Pruner((out,), retention_minutes=180, retention_ticks=5).sweep(state, NOW)
    assert pruned.emitted_total == 7
    assert pruned.last_error == "boom"
