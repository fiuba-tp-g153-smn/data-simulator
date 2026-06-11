"""Value objects describing what a single tick will emit."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from data_simulator.state.models import SourceState


class EmitMode(Enum):
    """How a seed file becomes an emitted file."""

    LINK = "link"
    COPY_GLM_REWRITE = "copy_glm_rewrite"


@dataclass(frozen=True, slots=True)
class FileMapping:
    """One seed file mapped to one destination file."""

    src: Path
    dst: Path
    mode: EmitMode
    coverage_start: datetime | None = None
    coverage_end: datetime | None = None


@dataclass(frozen=True, slots=True)
class TickPlan:
    """Pure description of a tick: mappings to emit plus the post-tick state."""

    tick: datetime
    mappings: tuple[FileMapping, ...]
    next_state: SourceState
