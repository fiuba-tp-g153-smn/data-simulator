"""Injectable clock so tick logic stays testable."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone


class Clock(ABC):
    """Source of the current UTC time."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC datetime."""


class SystemClock(Clock):
    """Wall-clock implementation."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
