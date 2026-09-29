#!/usr/bin/env python3
"""
Pre-flight check for morning systemd service.
Exits 0 if today is a regular trading day (Monday-Friday, non-holiday).
Exits 1 if today is a weekend or an official trading holiday, preventing service start.
"""
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils.holidays import is_trading_holiday

IST = ZoneInfo("Asia/Kolkata")


def main() -> int:
    now_ist = datetime.now(IST)
    today = now_ist.date()

    # Check weekend (0=Monday .. 6=Sunday)
    if now_ist.weekday() >= 5:
        print(f"[HOLIDAY GUARD] Today is weekend ({now_ist.strftime('%A')}, {today}). Skipping startup.")
        return 1

    # Check trading holiday
    if is_trading_holiday(today):
        print(f"[HOLIDAY GUARD] Today {today} is an official NSE trading holiday. Skipping startup.")
        return 1

    print(f"[HOLIDAY GUARD] Today {today} ({now_ist.strftime('%A')}) is a valid trading day. Proceeding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
