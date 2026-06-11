"""GlmAttrRewriter against a real HDF5 file with fixed-length byte attrs."""

from datetime import datetime, timezone

import h5py
import numpy as np

from data_simulator.sources.glm.glm_attr_rewriter import GlmAttrRewriter


def _make_glm_like_file(path):
    with h5py.File(path, "w") as handle:
        # CG_GLM files carry fixed-length byte-string attrs; replicate that.
        handle.attrs["time_coverage_start"] = np.bytes_("2026-03-02T14:00:00.0Z")
        handle.attrs["time_coverage_end"] = np.bytes_("2026-03-02T14:01:00.0Z")
        handle.create_dataset("flash_extent_density", data=np.zeros((2, 2)))


def test_rewrite_replaces_coverage_attrs(tmp_path):
    target = tmp_path / "window.nc"
    _make_glm_like_file(target)

    start = datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 6, 11, 9, 1, tzinfo=timezone.utc)
    GlmAttrRewriter().rewrite(target, start, end)

    with h5py.File(target, "r") as handle:
        raw_start = handle.attrs["time_coverage_start"]
        raw_end = handle.attrs["time_coverage_end"]
    decoded_start = raw_start.decode() if isinstance(raw_start, bytes) else raw_start
    decoded_end = raw_end.decode() if isinstance(raw_end, bytes) else raw_end
    # Full new value, no fixed-length truncation, parseable as naive ISO.
    assert datetime.fromisoformat(decoded_start) == start.replace(tzinfo=None)
    assert datetime.fromisoformat(decoded_end) == end.replace(tzinfo=None)


def test_rewrite_preserves_data(tmp_path):
    target = tmp_path / "window.nc"
    _make_glm_like_file(target)
    GlmAttrRewriter().rewrite(
        target,
        datetime(2026, 6, 11, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 6, 11, 9, 1, tzinfo=timezone.utc),
    )
    with h5py.File(target, "r") as handle:
        assert handle["flash_extent_density"].shape == (2, 2)
