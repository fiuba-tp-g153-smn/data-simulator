"""IntaReplayer: station grouping, 120 km filtering, timestamp rewrite, emission."""

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
from data_simulator.state.models import SourceState

TICK = datetime(2026, 6, 11, 9, 10, tzinfo=timezone.utc)

# The station folder is the key: sample names (PAR) carry no radar token.
SEED = {
    "PAR/2026052115100400dBZ.vol": 240,
    "PAR/2026052115100400ZDR.vol": 240,
    "PAR/2026052115200400dBZ.vol": 240,
    "ANG/ANG2026061920000300dBZ.vol": 240,
    "ANG/ANG2026061920050300dBZ.vol": 120,  # interleaved short scan
    "ANG/ANG2026061920000300dBZ.azi": 240,  # not a volume
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
    for name in ("2026052115100400dBZ.vol", "PER2026061920000300RhoHV.vol"):
        assert build_inta_filename(parse_inta_filename(name)) == name


def test_rejects_azi_and_foreign_names():
    for name in ("2026052115100400dBZ.azi", "RMA1_0315_01_DBZH_20260114T170328Z.H5"):
        with pytest.raises(ValueError):
            parse_inta_filename(name)


def test_one_scan_per_station_per_tick(tmp_path):
    plan = _replayer(tmp_path).plan_tick(TICK, SourceState())
    names = sorted(str(m.dst.relative_to(tmp_path / "out")) for m in plan.mappings)
    assert names == [
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


def test_cursors_advance_per_station(tmp_path):
    plan = _replayer(tmp_path).plan_tick(TICK, SourceState())
    assert plan.next_state.cursors["PAR"].index == 1  # two 240 km scans
    assert plan.next_state.cursors["ANG"].index == 0  # one after filtering


def test_seed_without_publishable_scans_fails_discovery(tmp_path):
    with pytest.raises(ValueError, match="240 km"):
        _replayer(tmp_path, seed={"ANG/ANG2026061920050300dBZ.vol": 120})


def test_emit_hardlinks_files(tmp_path):
    replayer = _replayer(tmp_path)
    emitted = replayer.emit(replayer.plan_tick(TICK, SourceState()))
    assert len(emitted) == 3
    src = tmp_path / "seed" / "ANG" / "ANG2026061920000300dBZ.vol"
    dst = tmp_path / "out" / "ANG" / "ANG2026061109100000dBZ.vol"
    assert os.stat(dst).st_ino == os.stat(src).st_ino
