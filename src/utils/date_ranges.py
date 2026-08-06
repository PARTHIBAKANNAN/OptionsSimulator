"""Date-range presets for P&L summary/export queries — IST-aware, matching the IST timestamps
already used throughout the live engine (see src/trader.py's IST)."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

VALID_RANGES = {"today", "yesterday", "this_week", "last_week", "this_month", "30d", "60d", "90d", "custom"}


def resolve_range(key: str, start: date = None, end: date = None, now: datetime = None) -> tuple[date, date]:
    """Returns (start_date, end_date), inclusive on both ends. `now` is injectable for tests —
    defaults to the real current IST time."""
    if key not in VALID_RANGES:
        raise ValueError(f"Unknown range '{key}' — must be one of {sorted(VALID_RANGES)}")

    today = (now or datetime.now(IST)).date()

    if key == "custom":
        if start is None or end is None:
            raise ValueError("custom range requires both start and end")
        if start > end:
            raise ValueError("custom range's start must not be after end")
        return start, end
    if key == "today":
        return today, today
    if key == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if key == "this_week":
        monday = today - timedelta(days=today.weekday())
        return monday, today
    if key == "last_week":
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(days=7)
        last_sunday = this_monday - timedelta(days=1)
        return last_monday, last_sunday
    if key == "this_month":
        first_of_month = today.replace(day=1)
        return first_of_month, today

    # "30d"/"60d"/"90d" — N calendar days total, inclusive of today.
    days = int(key[:-1])
    return today - timedelta(days=days - 1), today
