"""Parse/build INTA Rainbow5 filenames and read the scan range off the header.

Format mirrored from tiles-processor src/models/rainbow_header.py:
``{RADAR}{YYYYMMDDHHMMSS}{NN}{VARIABLE}.{EXT}``, where ``.vol`` is a 240 km
volume and ``.azi`` a single-sweep long-range PPI. The radar token is optional —
production names carry it (``PAR2026061920000300dBZ.vol``), the SMN's samples
do not (``2026052115100400dBZ.vol``) — so it round-trips as-is and the station
is taken from the seed subfolder instead.
"""

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

_INTA_PATTERN = re.compile(
    r"^(?P<radar>[A-Za-z]*)(?P<timestamp>\d{14})(?P<sequence>\d{2})"
    r"(?P<variable>[A-Za-z]+)\.(?P<extension>(?i:vol|azi))$"
)

# tiles-processor reads the same window: <stoprange> sits after the <pargroup>
# block, ~18.7 KB into the file.
HEADER_WINDOW_BYTES = 32768
_STOP_RANGE_RE = re.compile(rb"<stoprange>([^<]*)</stoprange>")


@dataclass(frozen=True, slots=True)
class IntaFilenameParts:
    """Decomposed INTA filename.

    ``extension`` keeps the case it was found in, so the emitted name differs
    from the seed one only in the timestamp.
    """

    radar: str
    timestamp: datetime
    sequence: str
    variable: str
    extension: str

    @property
    def is_long_range(self) -> bool:
        return self.extension.lower() == "azi"

    def with_timestamp(self, timestamp: datetime) -> "IntaFilenameParts":
        return replace(self, timestamp=timestamp)


def parse_inta_filename(name: str) -> IntaFilenameParts:
    match = _INTA_PATTERN.match(name)
    if match is None:
        raise ValueError(f"Not an INTA .vol/.azi filename: {name}")
    timestamp = datetime.strptime(match.group("timestamp"), "%Y%m%d%H%M%S").replace(
        tzinfo=timezone.utc
    )
    return IntaFilenameParts(
        radar=match.group("radar"),
        timestamp=timestamp,
        sequence=match.group("sequence"),
        variable=match.group("variable"),
        extension=match.group("extension"),
    )


def build_inta_filename(parts: IntaFilenameParts) -> str:
    stamp = parts.timestamp.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{parts.radar}{stamp}{parts.sequence}{parts.variable}.{parts.extension}"


def read_stop_range_km(path: Path) -> float | None:
    """Scan range from the Rainbow5 header, or None when it carries none."""
    with open(path, "rb") as handle:
        match = _STOP_RANGE_RE.search(handle.read(HEADER_WINDOW_BYTES))
    if match is None:
        return None
    try:
        return float(match.group(1).strip())
    except ValueError:
        return None
