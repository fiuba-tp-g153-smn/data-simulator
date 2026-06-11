"""Contract every source replayer implements."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from feed_simulator.core.tick_plan import TickPlan
from feed_simulator.state.models import SourceState


class Replayer(ABC):
    """Plans and emits one source's files for clock-aligned ticks.

    ``plan_tick`` must stay pure (no filesystem writes) so it is unit-testable;
    all IO happens in ``emit``.
    """

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Stable identifier used in state, API and logs (glm|radar|wrf)."""

    @abstractmethod
    def discover_seed(self) -> None:
        """Build the immutable seed index. Raise on empty/unusable seed."""

    @abstractmethod
    def plan_tick(self, tick: datetime, state: SourceState) -> TickPlan:
        """Compute the file mappings for ``tick`` and the resulting state."""

    @abstractmethod
    def emit(self, plan: TickPlan) -> list[Path]:
        """Materialize the plan on disk; return the created destination paths."""
