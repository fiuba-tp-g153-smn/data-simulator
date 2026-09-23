"""Group INTA seed files into per-station series of 240 km scans."""

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

# Only these volumes are published by tiles-processor (INTA_STOP_RANGE_KM).
# Anguil and Pergamino interleave 120 km scans in the same folder; replaying
# them would spend every other tick on a scan the producer throws away.
PUBLISHED_STOP_RANGE_KM = 240.0


@dataclass(frozen=True, slots=True)
class IntaScan:
    """All variable files of one station sharing one scan timestamp."""

    timestamp: datetime
    files: tuple[Path, ...]


def group_inta_seed(
    files: list[Path], seed_dir: Path
) -> dict[str, tuple[IntaScan, ...]]:
    """Return ``{"PAR": (scan, scan, ...)}`` with scans in chronological order.

    The station key is the seed subfolder (``<seed>/PAR/*.vol``), falling back
    to the filename's radar token for flat files — the sample names carry none,
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
        station = _station_key(path, seed_dir, parts.radar)
        buckets[station][parts.timestamp].append(path)

    series: dict[str, tuple[IntaScan, ...]] = {}
    for station, scans in buckets.items():
        published = tuple(
            IntaScan(timestamp=ts, files=tuple(sorted(scans[ts])))
            for ts in sorted(scans)
            if _is_published_range(scans[ts])
        )
        skipped = len(scans) - len(published)
        if skipped:
            logger.info("INTA %s: skipped %d non-240 km scans", station, skipped)
        if published:
            series[station] = published
    return series


def _station_key(path: Path, seed_dir: Path, radar_token: str) -> str:
    if path.parent != seed_dir:
        return path.parent.name
    return radar_token.upper() or "UNKNOWN"


def _is_published_range(files: list[Path]) -> bool:
    return read_stop_range_km(sorted(files)[0]) == PUBLISHED_STOP_RANGE_KM
