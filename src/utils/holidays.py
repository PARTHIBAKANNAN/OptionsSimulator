"""
Trading holiday calendar utilities for NSE/BSE.
Loads official trading holidays from data/nse_holidays_2026.json.
"""
from datetime import date
import json
from pathlib import Path
from typing import Set

_HOLIDAYS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nse_holidays_2026.json"
_HOLIDAYS_CACHE: Set[str] = set()
_LOADED = False


def load_trading_holidays() -> Set[str]:
    """Loads trading holidays as ISO date strings ('YYYY-MM-DD')."""
    global _HOLIDAYS_CACHE, _LOADED
    if _LOADED:
        return _HOLIDAYS_CACHE

    if _HOLIDAYS_PATH.exists():
        try:
            data = json.loads(_HOLIDAYS_PATH.read_text(encoding="utf-8"))
            holidays = set()
            for year, entries in data.items():
                for item in entries:
                    d_str = item.get("date")
                    if d_str:
                        holidays.add(d_str.strip())
            _HOLIDAYS_CACHE = holidays
            _LOADED = True
            return _HOLIDAYS_CACHE
        except Exception:
            pass

    _LOADED = True
    return _HOLIDAYS_CACHE


def is_trading_holiday(check_date: date) -> bool:
    """Returns True if the given date is an official trading holiday."""
    holidays = load_trading_holidays()
    return check_date.isoformat() in holidays
