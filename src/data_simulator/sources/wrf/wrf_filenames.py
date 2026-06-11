"""Parse/build WRF-ARG4K filenames.

Format mirrored from tiles-processor src/models/wrf_config.py:
``WRF_ARG4K.FCST_L0_{FIELD}.01H.{INIT_TAG}.{FXXX}.M000.nc`` with INIT_TAG like
``20260603_000000``. The pipeline discovers FIELD2D and derives the FIELD3D
sibling by string replacement, so both must exist with matching names.
"""

import re
from dataclasses import dataclass

_WRF_PATTERN = re.compile(
    r"^WRF_ARG4K\.FCST_L0_(?P<field>FIELD2D|FIELD3D)\.01H"
    r"\.(?P<init_tag>\d{8}_\d{6})\.F(?P<fnum>\d{3})\.M000\.nc$"
)


@dataclass(frozen=True, slots=True)
class WrfFilenameParts:
    """Decomposed WRF filename."""

    field: str
    init_tag: str
    fnum: int


def parse_wrf_filename(name: str) -> WrfFilenameParts:
    match = _WRF_PATTERN.match(name)
    if match is None:
        raise ValueError(f"Not a WRF FIELD2D/FIELD3D filename: {name}")
    return WrfFilenameParts(
        field=match.group("field"),
        init_tag=match.group("init_tag"),
        fnum=int(match.group("fnum")),
    )


def build_wrf_filename(parts: WrfFilenameParts) -> str:
    return (
        f"WRF_ARG4K.FCST_L0_{parts.field}.01H"
        f".{parts.init_tag}.F{parts.fnum:03d}.M000.nc"
    )


def derive_field3d_name(field2d_name: str) -> str:
    return field2d_name.replace("FIELD2D", "FIELD3D")
