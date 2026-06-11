"""Group WRF seed files into forecast runs and check completeness."""

import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from feed_simulator.sources.wrf.wrf_filenames import (
    derive_field3d_name,
    parse_wrf_filename,
)

logger = logging.getLogger(__name__)

EXPECTED_FORECAST_HOURS = 72


@dataclass(frozen=True, slots=True)
class WrfRun:
    """One complete forecast run: FIELD2D + FIELD3D files for F000..F072."""

    init_tag: str
    files: tuple[Path, ...]


def discover_complete_runs(
    seed_dir: Path, expected_hours: int = EXPECTED_FORECAST_HOURS
) -> tuple[WrfRun, ...]:
    """Return complete runs sorted by init tag; incomplete runs are skipped.

    Complete = FIELD2D present for every F000..F{expected_hours} AND the
    derived FIELD3D sibling exists for each (the worker opens FIELD3D on
    demand; a missing one fails the job mid-processing).
    """
    field2d_by_run: dict[str, dict[int, Path]] = defaultdict(dict)
    for path in seed_dir.glob("WRF_ARG4K.FCST_L0_FIELD2D.*.nc"):
        parts = parse_wrf_filename(path.name)
        field2d_by_run[parts.init_tag][parts.fnum] = path

    runs = []
    for init_tag in sorted(field2d_by_run):
        run = _build_run(init_tag, field2d_by_run[init_tag], expected_hours)
        if run is not None:
            runs.append(run)
    return tuple(runs)


def _build_run(
    init_tag: str, field2d: dict[int, Path], expected_hours: int
) -> WrfRun | None:
    missing_hours = set(range(expected_hours + 1)) - set(field2d)
    if missing_hours:
        logger.warning(
            "Skipping WRF run %s: missing FIELD2D hours %s",
            init_tag,
            sorted(missing_hours)[:5],
        )
        return None

    files: list[Path] = []
    for fnum in sorted(field2d):
        field2d_path = field2d[fnum]
        field3d_path = field2d_path.with_name(derive_field3d_name(field2d_path.name))
        if not field3d_path.exists():
            logger.warning(
                "Skipping WRF run %s: missing FIELD3D for F%03d", init_tag, fnum
            )
            return None
        files.extend((field2d_path, field3d_path))
    return WrfRun(init_tag=init_tag, files=tuple(files))
