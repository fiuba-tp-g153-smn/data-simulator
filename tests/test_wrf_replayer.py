"""WrfReplayer: run rotation, INIT_TAG rewrite, hardlink emission."""

import os
from datetime import datetime, timezone
from pathlib import Path

from data_simulator.core.emitter import FileEmitter
from data_simulator.sources.wrf.wrf_filenames import derive_field3d_name
from data_simulator.sources.wrf.wrf_replayer import WrfReplayer
from data_simulator.state.models import SourceState

SLOT = datetime(2026, 6, 11, 6, 0, tzinfo=timezone.utc)


def _make_run(seed_dir: Path, init_tag: str, hours: int = 2):
    seed_dir.mkdir(parents=True, exist_ok=True)
    for fnum in range(hours + 1):
        name2d = f"WRF_ARG4K.FCST_L0_FIELD2D.01H.{init_tag}.F{fnum:03d}.M000.nc"
        (seed_dir / name2d).write_bytes(b"nc")
        (seed_dir / derive_field3d_name(name2d)).write_bytes(b"nc")


def _replayer(tmp_path: Path) -> WrfReplayer:
    seed_dir = tmp_path / "seed"
    _make_run(seed_dir, "20260602_180000")
    _make_run(seed_dir, "20260603_000000")
    replayer = WrfReplayer(
        seed_dir=seed_dir,
        dest_dir=tmp_path / "out",
        emitter=FileEmitter("hardlink"),
        expected_hours=2,
    )
    replayer.discover_seed()
    return replayer


def test_plan_rewrites_init_tag_for_all_files(tmp_path):
    replayer = _replayer(tmp_path)
    plan = replayer.plan_tick(SLOT, SourceState())
    assert len(plan.mappings) == 6  # 3 FIELD2D + 3 FIELD3D
    assert all(".20260611_060000." in m.dst.name for m in plan.mappings)
    fields = {m.dst.name.split(".")[1] for m in plan.mappings}
    assert fields == {"FCST_L0_FIELD2D", "FCST_L0_FIELD3D"}


def test_run_rotation_ping_pongs(tmp_path):
    replayer = _replayer(tmp_path)
    state = SourceState()
    seen_runs = []
    for i in range(4):
        plan = replayer.plan_tick(SLOT, state)
        src_tag = plan.mappings[0].src.name.split(".")[3]
        seen_runs.append(src_tag)
        state = plan.next_state
    assert seen_runs == [
        "20260602_180000",
        "20260603_000000",
        "20260602_180000",
        "20260603_000000",
    ]


def test_emit_hardlinks_into_flat_dest(tmp_path):
    replayer = _replayer(tmp_path)
    plan = replayer.plan_tick(SLOT, SourceState())
    emitted = replayer.emit(plan)
    assert len(emitted) == 6
    assert all(p.parent == tmp_path / "out" for p in emitted)
    assert os.stat(emitted[0]).st_nlink == 2
