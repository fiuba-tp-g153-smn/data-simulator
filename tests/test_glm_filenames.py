"""GLM filename parse/build."""

from datetime import datetime, timezone

import pytest

from feed_simulator.sources.glm.glm_filenames import (
    GlmFilenameParts,
    build_glm_filename,
    parse_glm_filename,
)

SEED_NAME = "CG_GLM-L2-GLMF-M3_G19_s20260611400000_e20260611401000_c20260611402030.nc"


def test_parse_seed_name():
    parts = parse_glm_filename(SEED_NAME)
    assert parts.mode == "M3"
    assert parts.platform == "G19"
    assert parts.start == datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc)
    assert parts.end == datetime(2026, 3, 2, 14, 1, 0, tzinfo=timezone.utc)


def test_build_sets_created_after_end():
    parts = GlmFilenameParts(
        mode="M3",
        platform="G19",
        start=datetime(2026, 6, 11, 14, 0, 0, tzinfo=timezone.utc),
        end=datetime(2026, 6, 11, 14, 1, 0, tzinfo=timezone.utc),
    )
    name = build_glm_filename(parts)
    assert name == (
        "CG_GLM-L2-GLMF-M3_G19_s20261621400000_e20261621401000_c20261621401200.nc"
    )


def test_build_parse_roundtrip():
    parts = GlmFilenameParts(
        mode="M3",
        platform="G19",
        start=datetime(2026, 6, 11, 14, 0, 0, tzinfo=timezone.utc),
        end=datetime(2026, 6, 11, 14, 1, 0, tzinfo=timezone.utc),
    )
    reparsed = parse_glm_filename(build_glm_filename(parts))
    assert reparsed == parts


def test_parse_rejects_other_files():
    with pytest.raises(ValueError):
        parse_glm_filename("RMA1_0315_01_DBZH_20260114T170328Z.H5")
