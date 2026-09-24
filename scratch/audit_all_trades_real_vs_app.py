import json
import csv
from datetime import datetime, date, timedelta
from pathlib import Path
import zoneinfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IST = zoneinfo.ZoneInfo("Asia/Kolkata")

def main():
    # 1. Load trades
    with open(PROJECT_ROOT / "data" / "market_analysis" / "trades_sept01_to_date.json", "r") as f:
        trades = json.load(f)
        
    # 2. Load 1m candles
    with open(PROJECT_ROOT / "data" / "historical" / "all_option_contracts_candles_sept01_to_date.json", "r") as f:
        candle_data = json.load(f)["data"]
        
    print(f"Loaded {len(trades)} trades and {len(candle_data)} contract series.")
    
    audited_trades = []
    
    for i, t in enumerate(trades, 1):
        order_id = t["order_id"]
        strategy = t["strategy"]
        symbol = t["symbol"]
        qty = t["qty"] * t["lot_size"]
        lot_size = t["lot_size"]
        app_entry = t["entry_price"]
        app_exit = t["exit_price"] if t["exit_price"] else app_entry
        app_gross_pnl = t["gross_pnl"]
        app_charges = t["charges"]
        app_net_pnl = t["net_pnl"]
        app_reason = t["exit_reason"] or "N/A"
        
        entry_dt = datetime.strptime(t["entry_time_ist"], "%Y-%m-%d %H:%M:%S")
        exit_dt = datetime.strptime(t["exit_time_ist"], "%Y-%m-%d %H:%M:%S") if t["exit_time_ist"] != "OPEN" else entry_dt + timedelta(hours=2)
        trade_date = entry_dt.date()
        
        # Get candles for this contract
        c_info = candle_data.get(symbol, {})
        raw_candles = c_info.get("candles", [])
        
        # Filter candles for trade date
        day_candles = []
        for c in raw_candles:
            # c["timestamp"] is ISO string
            dt = datetime.fromisoformat(c["timestamp"])
            if dt.date() == trade_date:
                day_candles.append({
                    "dt": dt,
                    "open": c["open"],
                    "high": c["high"],
                    "low": c["low"],
                    "close": c["close"],
                    "volume": c["volume"]
                })
                
        # Find entry candle at entry_dt (or closest)
        entry_candle = None
        for c in day_candles:
            if abs((c["dt"] - entry_dt).total_seconds()) <= 60:
                entry_candle = c
                break
        if not entry_candle and day_candles:
            entry_candle = min(day_candles, key=lambda c: abs((c["dt"] - entry_dt).total_seconds()))
            
        real_entry = entry_candle["open"] if entry_candle else app_entry
        entry_diff_pct = abs(app_entry - real_entry) / real_entry * 100 if real_entry > 0 else 0.0
        
        # Simulate execution
        trade_candles = [c for c in day_candles if c["dt"] >= entry_candle["dt"]] if entry_candle else []
        
        sl_price = real_entry * 0.80  # 20% SL
        tp_price = real_entry * 1.50  # 50% TP
        trailing_active = False
        peak_price = real_entry
        real_exit = real_entry
        real_reason = "TIME_EXIT"
        real_exit_dt = entry_dt + timedelta(hours=2)
        
        for c in trade_candles:
            c_dt = c["dt"]
            c_high = c["high"]
            c_low = c["low"]
            c_close = c["close"]
            
            elapsed_mins = (c_dt - entry_dt).total_seconds() / 60.0
            
            if c_high > peak_price:
                peak_price = c_high
                
            # Trailing stop logic
            if peak_price >= real_entry * 1.10:
                trailing_active = True
                trail_sl = max(real_entry, peak_price * 0.90)
                if trail_sl > sl_price:
                    sl_price = trail_sl
                    
            # Check Stop Loss / Trailing Stop
            if c_low <= sl_price:
                real_exit = sl_price
                real_reason = "TRAILING_STOP" if trailing_active else "STOP_LOSS"
                real_exit_dt = c_dt
                break
                
            # Check Take Profit
            if c_high >= tp_price:
                real_exit = tp_price
                real_reason = "TAKE_PROFIT"
                real_exit_dt = c_dt
                break
                
            # Check Time Exit (120 mins or 15:15)
            if elapsed_mins >= 120 or c_dt.time() >= datetime.strptime("15:15", "%H:%M").time():
                real_exit = c_close
                real_reason = "TIME_EXIT"
                real_exit_dt = c_dt
                break
                
        real_gross_pnl = round((real_exit - real_entry) * qty, 2)
        real_net_pnl = round(real_gross_pnl - app_charges, 2)
        pnl_diff = round(real_gross_pnl - app_gross_pnl, 2)
        
        # Determine if trade was legitimate or distorted
        # Legit if entry variance <= 5% and data was not missing
        is_legit = entry_diff_pct <= 5.0 and len(day_candles) > 0
        status_flag = "LEGIT" if is_legit else "DISTORTED_DATA"
        
        audited_trades.append({
            "order_id": order_id,
            "date": str(trade_date),
            "strategy": strategy,
            "symbol": symbol,
            "lot_size": lot_size,
            "qty": qty,
            "in_time": entry_dt.strftime("%H:%M"),
            "app_in": round(app_entry, 2),
            "real_in": round(real_entry, 2),
            "entry_variance_pct": round(entry_diff_pct, 1),
            "out_time": real_exit_dt.strftime("%H:%M"),
            "app_out": round(app_exit, 2),
            "real_out": round(real_exit, 2),
            "app_reason": app_reason,
            "real_reason": real_reason,
            "app_gross_pnl": app_gross_pnl,
            "real_gross_pnl": real_gross_pnl,
            "pnl_diff": pnl_diff,
            "charges": app_charges,
            "real_net_pnl": real_net_pnl,
            "status": status_flag
        })

    # Save to CSV
    csv_path = PROJECT_ROOT / "data" / "market_analysis" / "audited_trades_real_vs_app_sept01_to_date.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(audited_trades[0].keys()))
        writer.writeheader()
        writer.writerows(audited_trades)
        
    # Save to JSON
    json_path = PROJECT_ROOT / "data" / "market_analysis" / "audited_trades_real_vs_app_sept01_to_date.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audited_trades, f, indent=2)
        
    # Print Daily Audit Summary
    print("\n" + "="*120)
    print(f"{'Date':<12} | {'Trades':<7} | {'Legit':<6} | {'Distorted':<9} | {'App Gross PnL':<15} | {'Real Gross PnL':<15} | {'Real Net PnL':<15} | {'Variance'}")
    print("="*120)
    
    daily_stats = {}
    total_app = 0.0
    total_real = 0.0
    total_charges = 0.0
    total_real_net = 0.0
    total_legit = 0
    total_distorted = 0
    
    for t in audited_trades:
        d = t["date"]
        if d not in daily_stats:
            daily_stats[d] = {
                "trades": 0, "legit": 0, "distorted": 0,
                "app_gross": 0.0, "real_gross": 0.0, "charges": 0.0, "real_net": 0.0
            }
        daily_stats[d]["trades"] += 1
        if t["status"] == "LEGIT":
            daily_stats[d]["legit"] += 1
            total_legit += 1
        else:
            daily_stats[d]["distorted"] += 1
            total_distorted += 1
            
        daily_stats[d]["app_gross"] += t["app_gross_pnl"]
        daily_stats[d]["real_gross"] += t["real_gross_pnl"]
        daily_stats[d]["charges"] += t["charges"]
        daily_stats[d]["real_net"] += t["real_net_pnl"]
        
        total_app += t["app_gross_pnl"]
        total_real += t["real_gross_pnl"]
        total_charges += t["charges"]
        total_real_net += t["real_net_pnl"]
        
    for d, st in sorted(daily_stats.items()):
        diff = st["real_gross"] - st["app_gross"]
        print(f"{d:<12} | {st['trades']:<7} | {st['legit']:<6} | {st['distorted']:<9} | Rs. {st['app_gross']:>11,.2f} | Rs. {st['real_gross']:>11,.2f} | Rs. {st['real_net']:>11,.2f} | Rs. {diff:>+11,.2f}")
        
    print("="*120)
    print(f"{'TOTAL':<12} | {len(audited_trades):<7} | {total_legit:<6} | {total_distorted:<9} | Rs. {total_app:>11,.2f} | Rs. {total_real:>11,.2f} | Rs. {total_real_net:>11,.2f} | Rs. {total_real - total_app:>+11,.2f}")
    print("="*120)

if __name__ == "__main__":
    main()
