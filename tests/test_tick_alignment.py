"""prev_aligned / next_aligned for 10-minute and 6-hour intervals."""

from datetime import datetime, timezone

from data_simulator.core.tick_alignment import next_aligned, prev_aligned


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_prev_aligned_10min():
    assert prev_aligned(_utc(2026, 6, 11, 14, 37, 12), 10) == _utc(2026, 6, 11, 14, 30)


def test_prev_aligned_on_boundary_is_identity():
    assert prev_aligned(_utc(2026, 6, 11, 14, 30), 10) == _utc(2026, 6, 11, 14, 30)


def test_next_aligned_10min():
    assert next_aligned(_utc(2026, 6, 11, 14, 37, 12), 10) == _utc(2026, 6, 11, 14, 40)


def test_next_aligned_on_boundary_is_next_step():
    assert next_aligned(_utc(2026, 6, 11, 14, 30), 10) == _utc(2026, 6, 11, 14, 40)


def test_prev_aligned_6h_slots():
    assert prev_aligned(_utc(2026, 6, 11, 5, 59), 360) == _utc(2026, 6, 11, 0, 0)
    assert prev_aligned(_utc(2026, 6, 11, 6, 0), 360) == _utc(2026, 6, 11, 6, 0)
    assert prev_aligned(_utc(2026, 6, 11, 17, 1), 360) == _utc(2026, 6, 11, 12, 0)
    assert prev_aligned(_utc(2026, 6, 11, 23, 59), 360) == _utc(2026, 6, 11, 18, 0)


def test_next_aligned_6h_day_rollover():
    assert next_aligned(_utc(2026, 6, 11, 19, 0), 360) == _utc(2026, 6, 12, 0, 0)


def test_next_aligned_10min_day_rollover():
    assert next_aligned(_utc(2026, 6, 11, 23, 55), 10) == _utc(2026, 6, 12, 0, 0)
