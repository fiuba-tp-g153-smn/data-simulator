"""GOES 14-char timestamp helpers (YYYYJJJHHMMSSD, D = deciseconds)."""

from datetime import datetime, timezone


def format_goes(dt: datetime) -> str:
    """Format a datetime as YYYYJJJHHMMSSD with the decisecond digit fixed to 0."""
    dt = dt.astimezone(timezone.utc) if dt.tzinfo else dt
    return f"{dt.year:04d}{dt.timetuple().tm_yday:03d}{dt:%H%M%S}0"


def parse_goes(stamp: str) -> datetime:
    """Parse YYYYJJJHHMMSSD into an aware UTC datetime (deciseconds dropped)."""
    if len(stamp) != 14:
        raise ValueError(f"GOES stamp must be 14 chars, got {stamp!r}")
    parsed = datetime.strptime(stamp[:13], "%Y%j%H%M%S")
    return parsed.replace(tzinfo=timezone.utc)
