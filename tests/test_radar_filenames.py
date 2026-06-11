"""Radar filename parse/build."""

from datetime import datetime, timezone

import pytest

from feed_simulator.sources.radar.radar_filenames import (
    build_radar_filename,
    parse_radar_filename,
)


def test_parse_seed_name():
    parts = parse_radar_filename("RMA1_0315_01_DBZH_20260114T170328Z.H5")
    assert parts.radar_id == "RMA1"
    assert parts.volume == "0315"
    assert parts.subvolume == "01"
    assert parts.variable == "DBZH"
    assert parts.timestamp == datetime(2026, 1, 14, 17, 3, 28, tzinfo=timezone.utc)


def test_parse_lowercase_extension_and_odd_volume():
    parts = parse_radar_filename("RMA5_9999_01_DBZH_20260114T183349Z.h5")
    assert parts.volume == "9999"


def test_build_with_new_timestamp():
    parts = parse_radar_filename("RMA12_0315_02_VRAD_20260114T170502Z.H5")
    renamed = parts.with_timestamp(
        datetime(2026, 6, 11, 9, 10, 20, tzinfo=timezone.utc)
    )
    assert build_radar_filename(renamed) == "RMA12_0315_02_VRAD_20260611T091020Z.H5"


def test_build_normalizes_extension_to_uppercase():
    parts = parse_radar_filename("RMA5_9999_01_DBZH_20260114T183349Z.h5")
    assert build_radar_filename(parts).endswith(".H5")


def test_parse_rejects_other_files():
    with pytest.raises(ValueError):
        parse_radar_filename("CG_GLM-L2-GLMF-M3_G19_s1_e2_c3.nc")
