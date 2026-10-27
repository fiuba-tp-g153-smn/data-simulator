"""Group INTA seed files into per-station series of published scans."""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from data_simulator.sources.inta.inta_filenames import (
    parse_inta_filename,
    read_stop_range_km,
)

logger = logging.getLogger(__name__)

# Mirrors tiles-processor's IntaScanSpec.accepts_range: volumes are published
# only at exactly 240 km and .azi PPIs only beyond it. Anguil and Pergamino
# interleave 120 km scans in the same folder; replaying them would spend every
# other tick on a scan the producer throws away.
PUBLISHED_STOP_RANGE_KM = 240.0

# Long-range PPIs get their own series (and cursor) next to the station's
# volumes: ``ANG`` holds the .vol scans, ``ANG/azi`` the .azi ones.
LONG_RANGE_SERIES_SUFFIX = "/azi"


@dataclass(frozen=True, slots=True)
class IntaScan:
    """All variable files of one station sharing one scan timestamp."""

    timestamp: datetime
    files: tuple[Path, ...]


def group_inta_seed(
    files: list[Path], seed_dir: Path
) -> dict[str, tuple[IntaScan, ...]]:
    """Return ``{"PAR": (scan, ...), "PAR/azi": (scan, ...)}``, scans in order.

    The station is the seed subfolder (``<seed>/PAR/*.vol``), falling back to
    the filename's radar token for flat files — the sample names carry none,
    so the folder is the only place the station is guaranteed to show up.
    """
    buckets: dict[str, dict[datetime, list[Path]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for path in files:
        try:
            parts = parse_inta_filename(path.name)
        except ValueError as exc:
            logger.debug("Skipping non-INTA file %s (%s)", path, exc)
            continue
        key = _station_key(path, seed_dir, parts.radar)
        if parts.is_long_range:
            key += LONG_RANGE_SERIES_SUFFIX
        buckets[key][parts.timestamp].append(path)

    series: dict[str, tuple[IntaScan, ...]] = {}
    for key, scans in buckets.items():
        published = tuple(
            IntaScan(timestamp=ts, files=tuple(sorted(scans[ts])))
            for ts in sorted(scans)
            if _is_published_range(scans[ts], is_long_range_series(key))
        )
        skipped = len(scans) - len(published)
        if skipped:
            logger.info("INTA %s: skipped %d unpublished-range scans", key, skipped)
        if published:
            series[key] = published
    return series


def is_long_range_series(key: str) -> bool:
    return key.endswith(LONG_RANGE_SERIES_SUFFIX)


def station_of(key: str) -> str:
    """Station folder a series emits into (``ANG/azi`` → ``ANG``)."""
    return key.removesuffix(LONG_RANGE_SERIES_SUFFIX)


def _station_key(path: Path, seed_dir: Path, radar_token: str) -> str:
    if path.parent != seed_dir:
        return path.parent.name
    return radar_token.upper() or "UNKNOWN"


def _is_published_range(files: list[Path], long_range: bool) -> bool:
    stop_range = read_stop_range_km(sorted(files)[0])
    if stop_range is None:
        return False
    if long_range:
        return stop_range > PUBLISHED_STOP_RANGE_KM
    return stop_range == PUBLISHED_STOP_RANGE_KM
