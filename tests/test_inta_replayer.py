"""IntaReplayer: station grouping, range filtering, timestamp rewrite, emission."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data_simulator.core.emitter import FileEmitter
from data_simulator.sources.inta.inta_filenames import (
    build_inta_filename,
    parse_inta_filename,
)
from data_simulator.sources.inta.inta_replayer import IntaReplayer
from data_simulator.state.models import CursorState, SourceState

TICK = datetime(2026, 6, 11, 9, 10, tzinfo=timezone.utc)

# The station folder is the key: sample names (PAR) carry no radar token.
SEED = {
    "PAR/2026052115100400dBZ.vol": 240,
    "PAR/2026052115100400ZDR.vol": 240,
    "PAR/2026052115200400dBZ.vol": 240,
    "ANG/ANG2026061920000300dBZ.vol": 240,
    "ANG/ANG2026061920050300dBZ.vol": 120,  # interleaved short scan
    "ANG/ANG2026061920072200dBZ.azi": 480,  # long-range PPI
    "ANG/ANG2026061920172200dBZ.azi": 240,  # not past 240 km: never published
}


def _header(stop_range: int) -> bytes:
    # <stoprange> sits past the 16 KB mark in the real files.
    return b"<pad/>" * 3000 + f"<stoprange>{stop_range}</stoprange>".encode()


def _replayer(tmp_path: Path, seed=SEED) -> IntaReplayer:
    seed_dir = tmp_path / "seed"
    for rel, stop_range in seed.items():
        path = seed_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_header(stop_range))
    replayer = IntaReplayer(
        seed_dir=seed_dir, dest_dir=tmp_path / "out", emitter=FileEmitter("hardlink")
    )
    replayer.discover_seed()
    return replayer


def test_filename_round_trips_with_and_without_radar_token():
    for name in (
        "2026052115100400dBZ.vol",
        "PER2026061920000300RhoHV.vol",
        "2026091501072200dBZ.azi",
        "ANG2026091501072200dBZ.AZI",
    ):
        assert build_inta_filename(parse_inta_filename(name)) == name


def test_azi_is_long_range_in_any_case():
    assert parse_inta_filename("2026091501072200dBZ.azi").is_long_range
    assert parse_inta_filename("2026091501072200dBZ.AZI").is_long_range
    assert not parse_inta_filename("2026091501072200dBZ.vol").is_long_range


def test_rejects_foreign_names():
    for name in (
        "2026052115100400dBZ.vol.bak",
        "2026052115100400dBZ.png",
        "RMA1_0315_01_DBZH_20260114T170328Z.H5",
    ):
        with pytest.raises(ValueError):
            parse_inta_filename(name)


def test_one_scan_per_station_per_tick(tmp_path):
    plan = _replayer(tmp_path).plan_tick(TICK, SourceState())
    names = sorted(str(m.dst.relative_to(tmp_path / "out")) for m in plan.mappings)
    assert names == [
        "ANG/ANG2026061109100000dBZ.azi",
        "ANG/ANG2026061109100000dBZ.vol",
        "PAR/2026061109100000ZDR.vol",
        "PAR/2026061109100000dBZ.vol",
    ]


def test_short_range_scans_are_never_replayed(tmp_path):
    replayer = _replayer(tmp_path)
    state = SourceState()
    for _ in range(3):
        plan = replayer.plan_tick(TICK, state)
        state = plan.next_state
        sources = {m.src.name for m in plan.mappings}
        assert "ANG2026061920050300dBZ.vol" not in sources
        assert "ANG2026061920172200dBZ.azi" not in sources


def test_cursors_advance_per_station(tmp_path):
    plan = _replayer(tmp_path).plan_tick(TICK, SourceState())
    assert plan.next_state.cursors["PAR"].index == 1  # two 240 km scans
    assert plan.next_state.cursors["ANG"].index == 0  # one after filtering
    assert plan.next_state.cursors["ANG/azi"].index == 0  # its own series
    assert "PAR/azi" not in plan.next_state.cursors  # no .azi in the seed


def test_state_from_before_the_azi_series_resumes(tmp_path):
    """A state.json written by the volume-only replayer keeps its cursors."""
    state = SourceState(cursors={"PAR": CursorState(index=1, direction=-1)})
    plan = _replayer(tmp_path).plan_tick(TICK, state)
    assert plan.next_state.cursors["PAR"].index == 0
    assert plan.next_state.cursors["ANG/azi"].index == 0


def test_seed_without_publishable_scans_fails_discovery(tmp_path):
    with pytest.raises(ValueError, match="240 km"):
        _replayer(tmp_path, seed={"ANG/ANG2026061920050300dBZ.vol": 120})


def test_long_range_scans_alone_do_not_make_a_seed(tmp_path):
    seed = {
        "ANG/ANG2026061920072200dBZ.azi": 480,
        "ANG/ANG2026061920000300dBZ.vol": 480,  # a volume must be 240 km
    }
    with pytest.raises(ValueError, match="240 km"):
        _replayer(tmp_path, seed=seed)


def test_seed_without_azi_warns_and_replays_volumes(tmp_path, caplog):
    seed = {"PAR/2026052115100400dBZ.vol": 240}
    with caplog.at_level(logging.WARNING):
        replayer = _replayer(tmp_path, seed=seed)
    assert "no long-range .azi" in caplog.text
    plan = replayer.plan_tick(TICK, SourceState())
    assert [m.dst.name for m in plan.mappings] == ["2026061109100000dBZ.vol"]


def test_uppercase_azi_is_discovered_and_keeps_its_case(tmp_path):
    seed = {
        "PER/2026091501000000dBZ.vol": 240,
        "PER/2026091501074200dBZ.AZI": 400,
    }
    plan = _replayer(tmp_path, seed=seed).plan_tick(TICK, SourceState())
    names = sorted(str(m.dst.relative_to(tmp_path / "out")) for m in plan.mappings)
    assert names == ["PER/2026061109100000dBZ.AZI", "PER/2026061109100000dBZ.vol"]


def test_emit_hardlinks_files(tmp_path):
    replayer = _replayer(tmp_path)
    emitted = replayer.emit(replayer.plan_tick(TICK, SourceState()))
    assert len(emitted) == 4
    src = tmp_path / "seed" / "ANG" / "ANG2026061920000300dBZ.vol"
    dst = tmp_path / "out" / "ANG" / "ANG2026061109100000dBZ.vol"
    assert os.stat(dst).st_ino == os.stat(src).st_ino


def test_emit_hardlinks_the_azi_into_its_station_folder(tmp_path):
    replayer = _replayer(tmp_path)
    replayer.emit(replayer.plan_tick(TICK, SourceState()))
    src = tmp_path / "seed" / "ANG" / "ANG2026061920072200dBZ.azi"
    dst = tmp_path / "out" / "ANG" / "ANG2026061109100000dBZ.azi"
    assert os.stat(dst).st_ino == os.stat(src).st_ino
