from datetime import UTC, date, datetime, time
from decimal import Decimal


def month_bounds(day: date) -> tuple[datetime, datetime]:
    first = day.replace(day=1)
    if first.month == 12:
        next_first = date(first.year + 1, 1, 1)
    else:
        next_first = date(first.year, first.month + 1, 1)

    start = datetime.combine(first, time.min, tzinfo=UTC)
    end = datetime.combine(next_first, time.min, tzinfo=UTC)
    return start, end


def calc_usage(
    limit: Decimal | None, spent: Decimal
) -> tuple[Decimal | None, Decimal | None]:
    if limit is None:
        return None, None

    remaining = limit - spent
    percent_used = ((spent / limit) * 100).quantize(Decimal("0.01"))
    return remaining, percent_used
