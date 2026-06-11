"""Reflecting cursor over a finite sequence (forward, then backward, no wrap jump)."""

from data_simulator.state.models import CursorState


class PingPongCursor:
    """Yields indices 0,1,..,n-1,n-2,..,0,1,.. (period 2n-2, endpoints not repeated)."""

    def __init__(self, length: int, state: CursorState | None = None) -> None:
        if length <= 0:
            raise ValueError("PingPongCursor requires a non-empty sequence")
        self._length = length
        state = state or CursorState()
        self._index = min(max(state.index, 0), length - 1)
        self._direction = -1 if state.direction < 0 else 1

    def step(self) -> int:
        """Return the current index, then advance with reflection at the ends."""
        current = self._index
        if self._length > 1:
            self._advance()
        return current

    def _advance(self) -> None:
        if self._index + self._direction in (-1, self._length):
            self._direction = -self._direction
        self._index += self._direction

    @property
    def direction(self) -> int:
        return self._direction

    def to_state(self) -> CursorState:
        return CursorState(index=self._index, direction=self._direction)
