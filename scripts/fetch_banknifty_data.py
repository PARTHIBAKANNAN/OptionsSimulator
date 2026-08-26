import sys
import os
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath("."))

headers = {'User-Agent': 'Mozilla/5.0'}

def fetch_banknifty_historical():
    print("Fetching Bank Nifty historical data from Yahoo Finance API...")
    # Fetch 5m candles (last 60 days) and 1h / 1d candles to synthesize 1-year dataset
    # For comprehensive 1-year backtest, fetch 1h resampled to 5m, or 60d 5m + 1y 1h
    
    # 1. Fetch 60d 5m data
    url_5m = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEBANK?range=60d&interval=5m"
    r_5m = requests.get(url_5m, headers=headers)
    data_5m = r_5m.json()
    chart_5m = data_5m['chart']['result'][0]
    ts_5m = chart_5m['timestamp']
    q_5m = chart_5m['indicators']['quote'][0]
    
    df_5m = pd.DataFrame({
        'Timestamp': [datetime.fromtimestamp(ts) for ts in ts_5m],
        'Open': q_5m['open'],
        'High': q_5m['high'],
        'Low': q_5m['low'],
        'Close': q_5m['close'],
        'Volume': [int(v or 0) for v in q_5m.get('volume', [0]*len(ts_5m))]
    }).dropna().sort_values('Timestamp').reset_index(drop=True)
    
    print(f"Fetched 60-day 5m data: {len(df_5m)} candles ({df_5m['Timestamp'].min()} to {df_5m['Timestamp'].max()})")
    
    # 2. Fetch 730d 1h data to cover the full 1 year (from Aug 2025 to Aug 2026)
    url_1h = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEBANK?range=730d&interval=1h"
    r_1h = requests.get(url_1h, headers=headers)
    data_1h = r_1h.json()
    chart_1h = data_1h['chart']['result'][0]
    ts_1h = chart_1h['timestamp']
    q_1h = chart_1h['indicators']['quote'][0]
    
    df_1h = pd.DataFrame({
        'Timestamp': [datetime.fromtimestamp(ts) for ts in ts_1h],
        'Open': q_1h['open'],
        'High': q_1h['high'],
        'Low': q_1h['low'],
        'Close': q_1h['close'],
        'Volume': [int(v or 0) for v in q_1h.get('volume', [0]*len(ts_1h))]
    }).dropna().sort_values('Timestamp').reset_index(drop=True)
    
    # Filter 1h data for 1 year (last 365 days)
    one_year_ago = datetime.now() - timedelta(days=365)
    df_1h_1y = df_1h[df_1h['Timestamp'] >= one_year_ago].copy()
    print(f"Fetched 1-year 1h data: {len(df_1h_1y)} candles ({df_1h_1y['Timestamp'].min()} to {df_1h_1y['Timestamp'].max()})")
    
    # Expand 1h candles into 5m resolution for the historical window prior to df_5m
    earliest_5m_ts = df_5m['Timestamp'].min()
    prior_1h = df_1h_1y[df_1h_1y['Timestamp'] < earliest_5m_ts]
    
    synthetic_5m = []
    for _, row in prior_1h.iterrows():
        base_ts = row['Timestamp']
        # 12 5m bars per 1h bar with smooth intraday distribution
        step_o = row['Open']
        step_h = row['High']
        step_l = row['Low']
        step_c = row['Close']
        v = row['Volume'] // 12
        for i in range(12):
            ts = base_ts + timedelta(minutes=5 * i)
            # interpolate price
            frac = i / 11.0 if 11 > 0 else 0
            interp_c = step_o + (step_c - step_o) * frac
            synthetic_5m.append({
                'Timestamp': ts,
                'Open': step_o if i == 0 else synthetic_5m[-1]['Close'],
                'High': max(step_o, step_h if i == 6 else interp_c),
                'Low': min(step_o, step_l if i == 3 else interp_c),
                'Close': step_c if i == 11 else interp_c,
                'Volume': v
            })
            
    df_synth = pd.DataFrame(synthetic_5m)
    full_5m_df = pd.concat([df_synth, df_5m]).drop_duplicates('Timestamp').sort_values('Timestamp').reset_index(drop=True)
    
    output_path = os.path.abspath("data/historical/banknifty_1year.csv")
    full_5m_df.to_csv(output_path, index=False)
    print(f"\nSaved complete 1-year Bank Nifty dataset to {output_path}")
    print(f"Total candles: {len(full_5m_df):,} | Date range: {full_5m_df['Timestamp'].min()} -> {full_5m_df['Timestamp'].max()}")
    return full_5m_df

if __name__ == "__main__":
    fetch_banknifty_historical()
