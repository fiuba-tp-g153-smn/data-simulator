"""RadarReplayer: per-group stepping, subvolume offsets, hardlink emission."""

import os
from datetime import datetime, timezone
from pathlib import Path

from data_simulator.core.emitter import FileEmitter
from data_simulator.sources.radar.radar_replayer import RadarReplayer
from data_simulator.state.models import SourceState

TICK = datetime(2026, 6, 11, 9, 10, tzinfo=timezone.utc)

SEED_NAMES = [
    "RMA1/RMA1_0315_01_DBZH_20260114T170328Z.H5",
    "RMA1/RMA1_0315_01_KDP_20260114T170328Z.H5",
    "RMA1/RMA1_0315_01_DBZH_20260114T171225Z.H5",
    "RMA1/RMA1_0315_01_KDP_20260114T171225Z.H5",
    "RMA1/RMA1_0315_04_DBZH_20260114T170308Z.H5",
    "RMA10/RMA10_0315_02_VRAD_20260114T182552Z.H5",
]


def _replayer(tmp_path: Path) -> RadarReplayer:
    seed_dir = tmp_path / "seed"
    for rel in SEED_NAMES:
        path = seed_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"h5")
    replayer = RadarReplayer(
        seed_dir=seed_dir, dest_dir=tmp_path / "out", emitter=FileEmitter("hardlink")
    )
    replayer.discover_seed()
    return replayer


def test_one_scan_per_group_per_tick(tmp_path):
    replayer = _replayer(tmp_path)
    plan = replayer.plan_tick(TICK, SourceState())
    # RMA1/01 scan (2 files) + RMA1/04 scan (1 file) + RMA10/02 scan (1 file)
    assert len(plan.mappings) == 4


def test_subvolume_offsets_applied(tmp_path):
    replayer = _replayer(tmp_path)
    plan = replayer.plan_tick(TICK, SourceState())
    names = sorted(m.dst.name for m in plan.mappings)
    assert "RMA1_0315_01_DBZH_20260611T091000Z.H5" in names
    assert "RMA1_0315_04_DBZH_20260611T091040Z.H5" in names
    assert "RMA10_0315_02_VRAD_20260611T091020Z.H5" in names


def test_destination_mirrors_per_radar_layout(tmp_path):
    replayer = _replayer(tmp_path)
    plan = replayer.plan_tick(TICK, SourceState())
    parents = {m.dst.parent.name for m in plan.mappings}
    assert parents == {"RMA1", "RMA10"}


def test_per_group_cursors_advance_independently(tmp_path):
    replayer = _replayer(tmp_path)
    plan = replayer.plan_tick(TICK, SourceState())
    cursors = plan.next_state.cursors
    assert cursors["RMA1/01"].index == 1  # two scans in this series
    assert cursors["RMA1/04"].index == 0  # single-scan series stays put
    assert cursors["RMA10/02"].index == 0


def test_emit_hardlinks_files(tmp_path):
    replayer = _replayer(tmp_path)
    plan = replayer.plan_tick(TICK, SourceState())
    emitted = replayer.emit(plan)
    assert len(emitted) == 4
    src_inode = os.stat(tmp_path / "seed" / SEED_NAMES[0]).st_ino
    dst = tmp_path / "out" / "RMA1" / "RMA1_0315_01_DBZH_20260611T091000Z.H5"
    assert os.stat(dst).st_ino == src_inode
