"""Rewrite the time_coverage_* attrs the worker-side aggregation reads.

tiles-processor src/services/glm_aggregation.py bins each file by its
``time_coverage_start``/``time_coverage_end`` global attrs against the
filename-derived window; stale attrs yield 0 time bins and a failed job, so
every replayed copy must carry attrs matching its new filename window.
"""

from datetime import datetime, timezone
from pathlib import Path

import h5py


class GlmAttrRewriter:
    """Updates coverage attrs in-place on an emitted copy (never on the seed)."""

    def rewrite(self, path: Path, start: datetime, end: datetime) -> None:
        with h5py.File(path, "r+") as handle:
            self._set_attr(handle, "time_coverage_start", start)
            self._set_attr(handle, "time_coverage_end", end)

    def _set_attr(self, handle: h5py.File, key: str, value: datetime) -> None:
        # Delete-then-set: attrs.modify would truncate to the original
        # fixed-length byte size. Naive ISO matches pd.Timestamp parsing
        # + tz_localize(None) on the consumer side.
        if key in handle.attrs:
            del handle.attrs[key]
        handle.attrs[key] = _naive_iso(value)


def _naive_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
