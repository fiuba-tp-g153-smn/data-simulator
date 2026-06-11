"""Clock-aligned tick computation (UTC, intervals as minutes since midnight)."""

from datetime import datetime, timedelta


def prev_aligned(now: datetime, interval_minutes: int) -> datetime:
    """Floor ``now`` to the latest multiple of ``interval_minutes`` past midnight UTC."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = now - midnight
    step = timedelta(minutes=interval_minutes)
    return midnight + step * (elapsed // step)


def next_aligned(now: datetime, interval_minutes: int) -> datetime:
    """First aligned tick strictly after ``now``."""
    return prev_aligned(now, interval_minutes) + timedelta(minutes=interval_minutes)
