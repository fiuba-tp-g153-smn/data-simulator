"""Group radar seed files into per-(radar, subvolume) series of scans."""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from data_simulator.sources.radar.radar_filenames import parse_radar_filename

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RadarScan:
    """All variable files of one radar/subvolume sharing one scan timestamp."""

    timestamp: datetime
    files: tuple[Path, ...]


def group_radar_seed(files: list[Path]) -> dict[str, tuple[RadarScan, ...]]:
    """Return ``{"RMA1/01": (scan, scan, ...)}`` with scans in chronological order.

    Each group has its own series because scan cadences and series lengths
    differ per radar and subvolume (absolute seed dates are irrelevant —
    replay rewrites every timestamp).
    """
    buckets: dict[str, dict[datetime, list[Path]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for path in files:
        try:
            parts = parse_radar_filename(path.name)
        except ValueError as exc:
            logger.debug("Skipping non-radar file %s (%s)", path, exc)
            continue
        key = f"{parts.radar_id}/{parts.subvolume}"
        buckets[key][parts.timestamp].append(path)

    return {
        key: tuple(
            RadarScan(timestamp=ts, files=tuple(sorted(scans[ts])))
            for ts in sorted(scans)
        )
        for key, scans in buckets.items()
    }
