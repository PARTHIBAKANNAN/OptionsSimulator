import json
import asyncio
import asyncpg
from datetime import datetime, timezone, timedelta
import zoneinfo

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

SYMBOL_MAP = {
    "SENSEX74900PE": "BSE:SENSEX2691774900PE",
    "SENSEX74400CE": "BSE:SENSEX2691774400CE",
    "SENSEX74300PE": "BSE:SENSEX2691774300PE",
    "SENSEX74800PE": "BSE:SENSEX2691774800PE",
    "NIFTY23250PE": "NSE:NIFTY2692223250PE",
    "BANKNIFTY56000PE": "NSE:BANKNIFTY26SEP56000PE",
    "NIFTY23200CE": "NSE:NIFTY2692223200CE",
    "NIFTY23300PE": "NSE:NIFTY2692223300PE",
    "SENSEX74300CE": "BSE:SENSEX2691774300CE",
    "SENSEX74200PE": "BSE:SENSEX2691774200PE",
    "NIFTY23200PE": "NSE:NIFTY2692223200PE",
    "BANKNIFTY55900CE": "NSE:BANKNIFTY26SEP55900CE",
    "SENSEX73700CE": "BSE:SENSEX2691773700CE",
}

async def main():
    # 1. Load candles
    with open('data/historical/option_contracts_candles_20260916.json', 'r') as f:
        data = json.load(f)
    all_candles = data.get('candles', {})
    
    # 2. Fetch recorded trades from Supabase
    url = 'postgresql://postgres.yovbqhkdzgzduknallbb:Thalamsd%407781@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres'
    conn = await asyncpg.connect(url, statement_cache_size=0)
    rows = await conn.fetch('''
        SELECT order_id, strategy, symbol, qty, lot_size, entry_price, entry_time, exit_price, exit_time, status, exit_reason, realized_pnl, stop_loss, take_profit
        FROM options_positions
        WHERE (exit_time::date = '2026-09-16' OR entry_time::date = '2026-09-16')
        ORDER BY entry_time ASC
    ''')
    await conn.close()
    
    print(f"Loaded {len(rows)} trades from 2026-09-16")
    
    results = []
    
    for r in rows:
        order_id = r['order_id']
        strategy = r['strategy']
        symbol = r['symbol']
        lot_size = r['lot_size']
        qty = r['qty'] * lot_size
        app_entry = float(r['entry_price'])
        app_exit = float(r['exit_price']) if r['exit_price'] else 0.0
        app_pnl = float(r['realized_pnl']) if r['realized_pnl'] else 0.0
        app_reason = r['exit_reason'] or 'N/A'
        
        raw_sym = SYMBOL_MAP.get(symbol)
        raw_candle_list = all_candles.get(raw_sym, [])
        
        entry_utc = r['entry_time']
        exit_utc = r['exit_time']
        entry_ist = entry_utc.astimezone(IST) if entry_utc.tzinfo else entry_utc.replace(tzinfo=timezone.utc).astimezone(IST)
        exit_ist = exit_utc.astimezone(IST) if exit_utc.tzinfo else exit_utc.replace(tzinfo=timezone.utc).astimezone(IST)
        
        # Filter candles for 2026-09-16
        day_candles = []
        for c in raw_candle_list:
            dt = datetime.fromisoformat(c['timestamp'])
            if dt.date() == entry_ist.date():
                day_candles.append({
                    "dt": dt,
                    "open": float(c['open']),
                    "high": float(c['high']),
                    "low": float(c['low']),
                    "close": float(c['close']),
                    "volume": int(c['volume']),
                })
                
        # Find exact entry candle (at entry_ist)
        entry_candle = None
        for c in day_candles:
            if abs((c['dt'] - entry_ist).total_seconds()) <= 60:
                entry_candle = c
                break
        if not entry_candle and day_candles:
            entry_candle = min(day_candles, key=lambda c: abs((c['dt'] - entry_ist).total_seconds()))
            
        real_entry_price = entry_candle['open'] if entry_candle else app_entry
        
        # Strategy execution simulation
        trade_candles = [c for c in day_candles if c['dt'] >= entry_candle['dt']] if entry_candle else []
        
        sl_price = real_entry_price * 0.80  # 20% SL
        tp_price = real_entry_price * 1.50  # 50% TP
        trailing_active = False
        peak_price = real_entry_price
        real_exit_price = real_entry_price
        real_exit_reason = "TIME_EXIT"
        real_exit_time = entry_ist + timedelta(hours=2)
        
        for c in trade_candles:
            c_dt = c['dt']
            c_open = c['open']
            c_high = c['high']
            c_low = c['low']
            c_close = c['close']
            
            elapsed_mins = (c_dt - entry_ist).total_seconds() / 60.0
            
            if c_high > peak_price:
                peak_price = c_high
                
            # Trailing stop logic: if profit > 10%, trail at max(entry, peak * 0.90)
            if peak_price >= real_entry_price * 1.10:
                trailing_active = True
                trail_sl = max(real_entry_price, peak_price * 0.90)
                if trail_sl > sl_price:
                    sl_price = trail_sl
                    
            # Check if Low hit SL / Trailing SL
            if c_low <= sl_price:
                real_exit_price = sl_price
                real_exit_reason = "TRAILING_STOP" if trailing_active else "STOP_LOSS"
                real_exit_time = c_dt
                break
                
            # Check if High hit TP
            if c_high >= tp_price:
                real_exit_price = tp_price
                real_exit_reason = "TAKE_PROFIT"
                real_exit_time = c_dt
                break
                
            # 2 Hour / 15:15 EOD exit
            if elapsed_mins >= 120 or c_dt.time() >= datetime.strptime("15:15", "%H:%M").time():
                real_exit_price = c_close
                real_exit_reason = "TIME_EXIT"
                real_exit_time = c_dt
                break
                
        real_pnl = (real_exit_price - real_entry_price) * qty
        diff = real_pnl - app_pnl
        
        results.append({
            "strategy": strategy,
            "symbol": symbol,
            "lot_size": lot_size,
            "qty": qty,
            "in_time": entry_ist.strftime("%H:%M"),
            "out_time_app": exit_ist.strftime("%H:%M"),
            "out_time_real": real_exit_time.strftime("%H:%M"),
            "app_entry": app_entry,
            "app_exit": app_exit,
            "app_reason": app_reason,
            "app_pnl": app_pnl,
            "real_entry": real_entry_price,
            "real_exit": real_exit_price,
            "real_reason": real_exit_reason,
            "real_pnl": real_pnl,
            "diff": diff
        })

    print("=" * 138)
    print(f"{'#':<3} | {'Strategy':<35} | {'Contract':<16} | {'Time':<6} | {'App In/Out (PnL)':<26} | {'Real In/Out (PnL)':<26} | {'PnL Diff':<10} | {'Real Exit Reason'}")
    print("=" * 138)
    
    tot_app = 0.0
    tot_real = 0.0
    real_wins = 0
    real_losses = 0
    real_be = 0
    
    for i, res in enumerate(results, 1):
        tot_app += res['app_pnl']
        tot_real += res['real_pnl']
        if res['real_pnl'] > 10:
            real_wins += 1
        elif res['real_pnl'] < -10:
            real_losses += 1
        else:
            real_be += 1
            
        app_str = f"{res['app_entry']:.1f}/{res['app_exit']:.1f} (Rs.{res['app_pnl']:>+6.0f})"
        real_str = f"{res['real_entry']:.1f}/{res['real_exit']:.1f} (Rs.{res['real_pnl']:>+6.0f})"
        time_str = f"{res['in_time']}"
        diff_str = f"Rs.{res['diff']:>+7.0f}"
        print(f"{i:<3} | {res['strategy'][:35]:<35} | {res['symbol']:<16} | {time_str:<6} | {app_str:<26} | {real_str:<26} | {diff_str:<10} | {res['real_reason']}")

    print("=" * 138)
    print(f"TOTAL APP RECORDED P&L (Synthetic/Distorted) : Rs. {tot_app:>10,.2f}")
    print(f"TOTAL REAL MARKET P&L  (Exact Market Data)    : Rs. {tot_real:>10,.2f}")
    print(f"NET PROFIT DIFFERENCE                         : Rs. {tot_real - tot_app:>+10,.2f}")
    print(f"REAL WIN RATE                                 : {real_wins} Wins / {real_losses} Losses / {real_be} Breakeven ({real_wins/len(results)*100:.1f}% Win Rate)")
    print("=" * 138)

if __name__ == '__main__':
    asyncio.run(main())
