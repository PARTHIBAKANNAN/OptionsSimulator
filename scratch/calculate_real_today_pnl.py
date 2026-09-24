import asyncio
import os
import sys
import json
from datetime import datetime, date, time, timezone, timedelta
from pathlib import Path
import zoneinfo
import asyncpg

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.fyers.api_client import FyersAPIClient
from src.utils.options_pricing import to_fyers_symbol

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

async def run_simulation():
    # 1. Fetch trades from Supabase
    url = 'postgresql://postgres.yovbqhkdzgzduknallbb:Thalamsd%407781@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres'
    conn = await asyncpg.connect(url, statement_cache_size=0)
    rows = await conn.fetch('''
        SELECT order_id, strategy, symbol, qty, lot_size, entry_price, entry_time, exit_price, exit_time, status, exit_reason, realized_pnl, stop_loss, take_profit
        FROM options_positions
        WHERE (exit_time::date = '2026-09-16' OR entry_time::date = '2026-09-16')
        ORDER BY entry_time ASC
    ''')
    await conn.close()
    
    print(f"Total trades fetched: {len(rows)}")
    
    # 2. Init Fyers client
    cfg = Config.load()
    fyers = FyersAPIClient(
        client_id=cfg.fyers_client_id,
        secret_key=cfg.fyers_secret_key,
        fy_id=cfg.fyers_fy_id,
        user_pin=cfg.fyers_user_pin,
        totp_secret=cfg.fyers_totp_secret,
        redirect_uri=cfg.fyers_redirect_uri,
    )
    fyers.authenticate_with_totp()
    
    # 3. Cache candles for each option symbol
    candle_cache = {}
    today_date = date(2026, 9, 16)
    
    # We will compute real performance
    real_results = []
    
    for r in rows:
        strat = r['strategy']
        simple_sym = r['symbol']
        lot_size = r['lot_size']
        qty = r['qty'] * lot_size
        recorded_entry = float(r['entry_price'])
        recorded_exit = float(r['exit_price']) if r['exit_price'] else 0.0
        recorded_pnl = float(r['realized_pnl']) if r['realized_pnl'] else 0.0
        recorded_reason = r['exit_reason']
        
        # Determine raw fyers symbol
        # Expired weekly on 16/17/18 Sep 2026
        # NIFTY weekly -> 26917, SENSEX weekly -> 26918 (or 26917), BANKNIFTY weekly -> 26922
        raw_symbol = None
        # Try finding via Fyers symbol format or direct query
        if "SENSEX" in simple_sym:
            # Try BSE:SENSEX26918... or BSE:SENSEX26SEP...
            raw_symbol = to_fyers_symbol(simple_sym, today_date)
        elif "BANKNIFTY" in simple_sym:
            raw_symbol = to_fyers_symbol(simple_sym, today_date)
        else:
            raw_symbol = to_fyers_symbol(simple_sym, today_date)
            
        if raw_symbol not in candle_cache:
            try:
                # fetch 1m candles for today
                candles = fyers.get_historical_data(raw_symbol, resolution="1", date_from="2026-09-16", date_to="2026-09-16")
                candle_cache[raw_symbol] = candles
            except Exception as e:
                print(f"Failed to fetch candles for {raw_symbol}: {e}")
                candle_cache[raw_symbol] = []
                
        candles = candle_cache[raw_symbol]
        
        # Convert entry/exit time to IST
        entry_utc = r['entry_time']
        exit_utc = r['exit_time']
        entry_ist = entry_utc.astimezone(IST) if entry_utc.tzinfo else entry_utc.replace(tzinfo=timezone.utc).astimezone(IST)
        exit_ist = exit_utc.astimezone(IST) if exit_utc.tzinfo else exit_utc.replace(tzinfo=timezone.utc).astimezone(IST)
        
        # Find candle at entry time
        real_entry_price = recorded_entry
        real_exit_price = recorded_exit
        real_reason = recorded_reason
        
        if candles:
            # candles are list of dicts or list of [ts, o, h, l, c, v]
            # Find candle closest to entry_ist
            # Let's see candle format
            entry_ts = entry_ist.timestamp()
            exit_ts = exit_ist.timestamp()
            
            # Map candles to minute timestamp
            matching_entry = None
            matching_exit = None
            
            for c in candles:
                c_ts = c[0] if isinstance(c, (list, tuple)) else c.get('timestamp')
                c_o = c[1] if isinstance(c, (list, tuple)) else c.get('open')
                c_h = c[2] if isinstance(c, (list, tuple)) else c.get('high')
                c_l = c[3] if isinstance(c, (list, tuple)) else c.get('low')
                c_c = c[4] if isinstance(c, (list, tuple)) else c.get('close')
                
                # Check entry candle (within 60 seconds)
                if abs(c_ts - entry_ts) <= 60 and matching_entry is None:
                    matching_entry = c_c
                if abs(c_ts - exit_ts) <= 60 and matching_exit is None:
                    matching_exit = c_c
                    
            if matching_entry:
                real_entry_price = float(matching_entry)
            if matching_exit:
                real_exit_price = float(matching_exit)
                
        real_pnl = (real_exit_price - real_entry_price) * qty
        real_results.append({
            "strategy": strat,
            "symbol": simple_sym,
            "raw_symbol": raw_symbol,
            "entry_time": entry_ist.strftime("%H:%M:%S"),
            "exit_time": exit_ist.strftime("%H:%M:%S"),
            "recorded_entry": recorded_entry,
            "recorded_exit": recorded_exit,
            "recorded_pnl": recorded_pnl,
            "recorded_reason": recorded_reason,
            "real_entry": real_entry_price,
            "real_exit": real_exit_price,
            "real_pnl": real_pnl,
            "real_reason": real_reason,
            "qty": qty,
        })
        
    print("\n" + "="*110)
    print(f"{'Strategy':<35} | {'Symbol':<15} | {'Time':<17} | {'App PnL':<10} | {'Real PnL':<10} | {'Diff'}")
    print("="*110)
    
    tot_rec = 0.0
    tot_real = 0.0
    for res in real_results:
        tot_rec += res['recorded_pnl']
        tot_real += res['real_pnl']
        diff = res['real_pnl'] - res['recorded_pnl']
        t_str = f"{res['entry_time']}->{res['exit_time']}"
        print(f"{res['strategy'][:35]:<35} | {res['symbol']:<15} | {t_str:<17} | Rs.{res['recorded_pnl']:>7.2f} | Rs.{res['real_pnl']:>7.2f} | Rs.{diff:>+7.2f}")
        
    print("="*110)
    print(f"TOTAL RECORDED APP P&L : Rs. {tot_rec:,.2f}")
    print(f"TOTAL REAL MARKET P&L  : Rs. {tot_real:,.2f}")
    print(f"NET PERFORMANCE SHIFT  : Rs. {tot_real - tot_rec:>+,.2f}")
    print("="*110)

if __name__ == '__main__':
    asyncio.run(run_simulation())
