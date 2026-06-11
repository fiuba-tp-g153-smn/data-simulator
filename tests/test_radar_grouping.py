"""Radar seed grouping into per-(radar, subvolume) scan series."""

from pathlib import Path

from feed_simulator.sources.radar.radar_grouping import group_radar_seed


def _paths(*names: str) -> list[Path]:
    return [Path("/seed/radar_h5") / n.split("_")[0] / n for n in names]


def test_groups_by_radar_and_subvolume():
    series = group_radar_seed(
        _paths(
            "RMA1_0315_01_DBZH_20260114T170328Z.H5",
            "RMA1_0315_01_KDP_20260114T170328Z.H5",
            "RMA1_0315_02_VRAD_20260114T170821Z.H5",
            "RMA10_0315_01_DBZH_20260114T183002Z.H5",
        )
    )
    assert set(series) == {"RMA1/01", "RMA1/02", "RMA10/01"}
    assert len(series["RMA1/01"]) == 1
    assert len(series["RMA1/01"][0].files) == 2


def test_scans_sorted_chronologically_with_unequal_lengths():
    series = group_radar_seed(
        _paths(
            "RMA1_0315_01_DBZH_20260114T171225Z.H5",
            "RMA1_0315_01_DBZH_20260114T170328Z.H5",
            "RMA1_0315_01_DBZH_20260114T172123Z.H5",
            "RMA18_0315_01_DBZH_20260310T111008Z.H5",  # different date than RMA1
        )
    )
    timestamps = [scan.timestamp for scan in series["RMA1/01"]]
    assert timestamps == sorted(timestamps)
    assert len(series["RMA1/01"]) == 3
    assert len(series["RMA18/01"]) == 1


def test_non_radar_files_skipped():
    series = group_radar_seed(
        _paths("RMA1_0315_01_DBZH_20260114T170328Z.H5") + [Path("/seed/notes.txt")]
    )
    assert set(series) == {"RMA1/01"}
