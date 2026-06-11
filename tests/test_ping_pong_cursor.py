"""PingPongCursor: reflection sequence, edge sizes, state roundtrip."""

import pytest

from data_simulator.core.ping_pong_cursor import PingPongCursor
from data_simulator.state.models import CursorState


def _take(cursor: PingPongCursor, count: int) -> list[int]:
    return [cursor.step() for _ in range(count)]


def test_reflection_sequence_n4():
    cursor = PingPongCursor(4)
    assert _take(cursor, 10) == [0, 1, 2, 3, 2, 1, 0, 1, 2, 3]


def test_period_is_2n_minus_2():
    cursor = PingPongCursor(5)
    period = 2 * 5 - 2
    first = _take(cursor, period)
    second = _take(cursor, period)
    assert first == second
    assert first == [0, 1, 2, 3, 4, 3, 2, 1]


def test_no_endpoint_repetition():
    cursor = PingPongCursor(3)
    seq = _take(cursor, 9)
    for a, b in zip(seq, seq[1:]):
        assert a != b


def test_single_element_stays():
    cursor = PingPongCursor(1)
    assert _take(cursor, 4) == [0, 0, 0, 0]


def test_two_elements_alternate():
    cursor = PingPongCursor(2)
    assert _take(cursor, 5) == [0, 1, 0, 1, 0]


def test_state_roundtrip_resumes_sequence():
    cursor = PingPongCursor(4)
    expected = _take(cursor, 10)

    replay = PingPongCursor(4)
    actual = []
    for _ in range(10):
        actual.append(replay.step())
        replay = PingPongCursor(4, state=replay.to_state())
    assert actual == expected


def test_direction_before_step_reflects_travel():
    cursor = PingPongCursor(3)
    directions = []
    for _ in range(6):
        directions.append(cursor.direction)
        cursor.step()
    # Emitting 0,1,2,1,0,1 — the peak (2) is still emitted while traveling forward.
    assert directions == [1, 1, 1, -1, -1, 1]


def test_out_of_range_state_clamped():
    cursor = PingPongCursor(3, state=CursorState(index=99, direction=1))
    assert cursor.step() == 2


def test_empty_sequence_rejected():
    with pytest.raises(ValueError):
        PingPongCursor(0)
