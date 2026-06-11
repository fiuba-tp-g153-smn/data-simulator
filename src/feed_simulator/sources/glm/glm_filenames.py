"""Parse/build CG_GLM-L2-GLMF filenames.

Format mirrored from tiles-processor src/models/glm_folder_config.py:
``CG_GLM-L2-GLMF-{mode}_{platform}_s{START}_e{END}_c{CREATED}.nc`` with
START/END/CREATED as 14-char GOES stamps.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from feed_simulator.sources.goes_time import format_goes, parse_goes

_GLM_PATTERN = re.compile(
    r"^CG_GLM-L2-GLMF-(?P<mode>M\d)_(?P<platform>G\d{2})"
    r"_s(?P<start>\d{14})_e(?P<end>\d{14})_c(?P<created>\d{14})\.nc$"
)

_CREATED_LAG = timedelta(seconds=20)


@dataclass(frozen=True, slots=True)
class GlmFilenameParts:
    """Decomposed GLM filename."""

    mode: str
    platform: str
    start: datetime
    end: datetime


def parse_glm_filename(name: str) -> GlmFilenameParts:
    match = _GLM_PATTERN.match(name)
    if match is None:
        raise ValueError(f"Not a GLM GLMF filename: {name}")
    return GlmFilenameParts(
        mode=match.group("mode"),
        platform=match.group("platform"),
        start=parse_goes(match.group("start")),
        end=parse_goes(match.group("end")),
    )


def build_glm_filename(parts: GlmFilenameParts) -> str:
    created = parts.end + _CREATED_LAG
    return (
        f"CG_GLM-L2-GLMF-{parts.mode}_{parts.platform}"
        f"_s{format_goes(parts.start)}"
        f"_e{format_goes(parts.end)}"
        f"_c{format_goes(created)}.nc"
    )
