"""Atomic JSON persistence for the simulator state."""

import json
import logging
import os
from pathlib import Path

from feed_simulator.state.models import SimState, state_from_dict, state_to_dict

logger = logging.getLogger(__name__)


class JsonStateStore:
    """Loads/saves SimState as one JSON file using tmp-file + os.replace."""

    def __init__(self, state_file: Path) -> None:
        self._state_file = state_file

    def load(self) -> SimState:
        if not self._state_file.exists():
            return SimState()
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
            return state_from_dict(payload)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Corrupt state file %s (%s) — starting fresh", self._state_file, exc
            )
            return SimState()

    def save(self, state: SimState) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._state_file.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(state_to_dict(state), indent=2), encoding="utf-8"
        )
        os.replace(tmp_path, self._state_file)
