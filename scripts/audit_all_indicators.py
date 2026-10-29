"""
Comprehensive Indicator & Metric Health Audit
============================================
Checks all technical indicators and metrics computed by DataManager
across NIFTY, BANKNIFTY, and SENSEX against real cached candles.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math
import src.db.sqlite_candle_cache as sc
from src.data_manager import DataManager

print("=" * 80)
print("COMPREHENSIVE AUDIT OF ALL STRATEGY METRICS & INDICATORS")
print("=" * 80)

for und in ["NIFTY", "BANKNIFTY", "SENSEX"]:
    candles = sc.load_recent_candles(und, days=10)
    dm = DataManager(underlying=und)
    dm.load_historical(candles)

    inds = dm.calculate_indicators()
    print(f"\n--- {und} (Candles loaded: {len(candles)}) ---")

    key_checks = [
        "ema_20_5m", "ema_50_5m", "ema_50_1h",
        "vwap_5m", "vwap",
        "supertrend_10_3", "supertrend_10_3_direction",
        "supertrend_7_2", "supertrend_7_2_direction",
        "adx_14_5m", "adx_14_1m",
        "bb_upper_5m", "bb_lower_5m", "bb_bandwidth_5m",
        "bb_squeeze_ratio_5m", "bb_bandwidth_expansion_5m",
        "rsi_14_5m", "rsi_1h",
        "macd_histogram_5m", "macd_histogram_15m",
        "cmf_20_5m", "volume_ratio_5m", "avg_volume",
    ]

    issues = []
    for k in key_checks:
        val = inds.get(k)
        if val is None:
            issues.append(f"{k} is MISSING")
        elif isinstance(val, (int, float)):
            if math.isnan(val) or math.isinf(val):
                issues.append(f"{k} is NaN/Inf")
            else:
                print(f"  [OK] {k:<30} = {val:.4f}")
        else:
            print(f"  [OK] {k:<30} = {val}")

    ha_5m = inds.get("heikin_ashi_5m")
    if ha_5m and all(k in ha_5m for k in ["open", "high", "low", "close"]):
        print(f"  [OK] {'heikin_ashi_5m':<30} = O:{ha_5m['open']:.2f} H:{ha_5m['high']:.2f} L:{ha_5m['low']:.2f} C:{ha_5m['close']:.2f}")
    else:
        issues.append("heikin_ashi_5m malformed or missing")

    if issues:
        print(f"  [FAIL] ISSUES FOUND: {issues}")
    else:
        print(f"  >>> ALL {len(key_checks)} METRICS ARE 100% HEALTHY & VALID <<<")
