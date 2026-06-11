"""GOES 14-char timestamp formatting and parsing."""

from datetime import datetime, timezone

import pytest

from data_simulator.sources.goes_time import format_goes, parse_goes


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_format_known_value():
    # 2026-06-11 14:00:00 UTC is day-of-year 162... no: matches the seed name
    # s20260611400000 -> 2026, day 061, 14:00:00.0
    assert format_goes(_utc(2026, 3, 2, 14, 0, 0)) == "20260611400000"


def test_roundtrip():
    dt = _utc(2026, 6, 11, 9, 21, 49)
    assert parse_goes(format_goes(dt)) == dt


def test_jan_first_and_dec_31():
    assert format_goes(_utc(2026, 1, 1, 0, 0, 0)) == "20260010000000"
    assert format_goes(_utc(2026, 12, 31, 23, 59, 59)) == "20263652359590"


def test_leap_year_day_of_year():
    assert format_goes(_utc(2024, 3, 1, 0, 0, 0)) == "20240610000000"
    assert format_goes(_utc(2026, 3, 1, 0, 0, 0)) == "20260600000000"


def test_parse_rejects_wrong_length():
    with pytest.raises(ValueError):
        parse_goes("2026061140000")
