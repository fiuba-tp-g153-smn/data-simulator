"""WRF filename parsing and run completeness."""

from pathlib import Path

import pytest

from feed_simulator.sources.wrf.wrf_filenames import (
    build_wrf_filename,
    derive_field3d_name,
    parse_wrf_filename,
)
from feed_simulator.sources.wrf.wrf_runs import discover_complete_runs


def _make_run(seed_dir: Path, init_tag: str, hours: int, skip_field3d_for=()):
    seed_dir.mkdir(parents=True, exist_ok=True)
    for fnum in range(hours + 1):
        name2d = f"WRF_ARG4K.FCST_L0_FIELD2D.01H.{init_tag}.F{fnum:03d}.M000.nc"
        (seed_dir / name2d).touch()
        if fnum not in skip_field3d_for:
            (seed_dir / derive_field3d_name(name2d)).touch()


def test_parse_and_build_roundtrip():
    name = "WRF_ARG4K.FCST_L0_FIELD2D.01H.20260603_000000.F042.M000.nc"
    parts = parse_wrf_filename(name)
    assert parts.field == "FIELD2D"
    assert parts.init_tag == "20260603_000000"
    assert parts.fnum == 42
    assert build_wrf_filename(parts) == name


def test_derive_field3d_name():
    assert derive_field3d_name(
        "WRF_ARG4K.FCST_L0_FIELD2D.01H.20260603_000000.F000.M000.nc"
    ) == "WRF_ARG4K.FCST_L0_FIELD3D.01H.20260603_000000.F000.M000.nc"


def test_parse_rejects_other_files():
    with pytest.raises(ValueError):
        parse_wrf_filename("RMA1_0315_01_DBZH_20260114T170328Z.H5")


def test_complete_runs_discovered_sorted(tmp_path):
    _make_run(tmp_path, "20260603_000000", hours=72)
    _make_run(tmp_path, "20260602_180000", hours=72)
    runs = discover_complete_runs(tmp_path)
    assert [r.init_tag for r in runs] == ["20260602_180000", "20260603_000000"]
    assert len(runs[0].files) == 146  # 73 FIELD2D + 73 FIELD3D


def test_partial_run_rejected(tmp_path):
    _make_run(tmp_path, "20260430_060000", hours=6)
    _make_run(tmp_path, "20260603_000000", hours=72)
    runs = discover_complete_runs(tmp_path)
    assert [r.init_tag for r in runs] == ["20260603_000000"]


def test_run_with_missing_field3d_rejected(tmp_path):
    _make_run(tmp_path, "20260603_000000", hours=72, skip_field3d_for={40})
    assert discover_complete_runs(tmp_path) == ()
