"""Parse/build SINARAME radar filenames.

Format mirrored from tiles-processor src/models/radar_config.py:
``{RADAR}_{VOLUME}_{SUBVOLUME}_{VARIABLE}_{YYYYMMDD}T{HHMMSS}Z.H5``
"""

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone

_RADAR_PATTERN = re.compile(
    r"^(?P<radar_id>[A-Z0-9]+)_(?P<volume>\d{4})_(?P<subvolume>\d{2})"
    r"_(?P<variable>[A-Z]+)_(?P<timestamp>\d{8}T\d{6})Z\.[hH]5$"
)


@dataclass(frozen=True, slots=True)
class RadarFilenameParts:
    """Decomposed radar filename."""

    radar_id: str
    volume: str
    subvolume: str
    variable: str
    timestamp: datetime

    def with_timestamp(self, timestamp: datetime) -> "RadarFilenameParts":
        return replace(self, timestamp=timestamp)


def parse_radar_filename(name: str) -> RadarFilenameParts:
    match = _RADAR_PATTERN.match(name)
    if match is None:
        raise ValueError(f"Not a radar H5 filename: {name}")
    timestamp = datetime.strptime(match.group("timestamp"), "%Y%m%dT%H%M%S").replace(
        tzinfo=timezone.utc
    )
    return RadarFilenameParts(
        radar_id=match.group("radar_id"),
        volume=match.group("volume"),
        subvolume=match.group("subvolume"),
        variable=match.group("variable"),
        timestamp=timestamp,
    )


def build_radar_filename(parts: RadarFilenameParts) -> str:
    stamp = parts.timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return (
        f"{parts.radar_id}_{parts.volume}_{parts.subvolume}"
        f"_{parts.variable}_{stamp}Z.H5"
    )
