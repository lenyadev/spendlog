from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest

from spendlog.budget import calc_usage, month_bounds

# ---------- month_bounds ----------


def test_month_bounds_regular_month():
    start, end = month_bounds(date(2024, 1, 15))
    assert start == datetime(2024, 1, 1, tzinfo=UTC)
    assert end == datetime(2024, 2, 1, tzinfo=UTC)


def test_month_bounds_30_day_month():
    start, end = month_bounds(date(2024, 4, 10))
    assert start == datetime(2024, 4, 1, tzinfo=UTC)
    assert end == datetime(2024, 5, 1, tzinfo=UTC)


def test_month_bounds_december_rolls_to_next_year():
    start, end = month_bounds(date(2024, 12, 15))
    assert start == datetime(2024, 12, 1, tzinfo=UTC)
    assert end == datetime(2025, 1, 1, tzinfo=UTC)


def test_month_bounds_february_non_leap():
    start, end = month_bounds(date(2023, 2, 15))
    assert start == datetime(2023, 2, 1, tzinfo=UTC)
    assert end == datetime(2023, 3, 1, tzinfo=UTC)


def test_month_bounds_february_leap():
    start, end = month_bounds(date(2024, 2, 29))
    assert start == datetime(2024, 2, 1, tzinfo=UTC)
    assert end == datetime(2024, 3, 1, tzinfo=UTC)


def test_month_bounds_first_day():
    start, end = month_bounds(date(2024, 6, 1))
    assert start == datetime(2024, 6, 1, tzinfo=UTC)
    assert end == datetime(2024, 7, 1, tzinfo=UTC)


def test_month_bounds_last_day():
    start, end = month_bounds(date(2024, 6, 30))
    assert start == datetime(2024, 6, 1, tzinfo=UTC)
    assert end == datetime(2024, 7, 1, tzinfo=UTC)


def test_month_bounds_returns_utc():
    start, end = month_bounds(date(2024, 6, 15))
    assert start.tzinfo is UTC
    assert end.tzinfo is UTC


def test_month_bounds_start_at_midnight():
    start, _ = month_bounds(date(2024, 6, 15))
    assert start.time() == time.min


def test_month_bounds_end_equals_next_month_start():
    _, end_jan = month_bounds(date(2024, 1, 20))
    start_feb, _ = month_bounds(date(2024, 2, 5))
    assert end_jan == start_feb


# ---------- calc_usage ----------


def test_calc_usage_none_limit():
    remaining, percent = calc_usage(None, Decimal("50"))
    assert remaining is None
    assert percent is None


def test_calc_usage_none_limit_zero_spent():
    remaining, percent = calc_usage(None, Decimal("0"))
    assert remaining is None
    assert percent is None


def test_calc_usage_typical():
    remaining, percent = calc_usage(Decimal("100"), Decimal("25"))
    assert remaining == Decimal("75")
    assert percent == Decimal("25.00")


def test_calc_usage_zero_spent():
    remaining, percent = calc_usage(Decimal("100"), Decimal("0"))
    assert remaining == Decimal("100")
    assert percent == Decimal("0.00")


def test_calc_usage_full():
    remaining, percent = calc_usage(Decimal("100"), Decimal("100"))
    assert remaining == Decimal("0")
    assert percent == Decimal("100.00")


def test_calc_usage_over_budget():
    remaining, percent = calc_usage(Decimal("100"), Decimal("150"))
    assert remaining == Decimal("-50")
    assert percent == Decimal("150.00")


def test_calc_usage_percent_rounds_down():
    remaining, percent = calc_usage(Decimal("3"), Decimal("1"))
    assert remaining == Decimal("2")
    assert percent == Decimal("33.33")


def test_calc_usage_percent_rounds_up():
    remaining, percent = calc_usage(Decimal("3"), Decimal("2"))
    assert remaining == Decimal("1")
    assert percent == Decimal("66.67")


def test_calc_usage_decimal_values():
    remaining, percent = calc_usage(Decimal("10.50"), Decimal("3.25"))
    assert remaining == Decimal("7.25")
    assert percent == Decimal("30.95")


def test_calc_usage_percent_has_two_places():
    _, percent = calc_usage(Decimal("7"), Decimal("1"))
    assert percent == Decimal("14.29")
    assert percent.as_tuple().exponent == -2


def test_calc_usage_zero_limit_raises():
    with pytest.raises(ZeroDivisionError):
        calc_usage(Decimal("0"), Decimal("10"))
