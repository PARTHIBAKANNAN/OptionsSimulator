import json
from pathlib import Path

# Load report.json
with open('data/backtest_results/report.json') as f:
    report = json.load(f)

items = [v for k, v in report.items() if isinstance(v, dict)]
tot_trades = sum(v.get('total_trades', 0) for v in items)
tot_pnl = sum(v.get('total_pnl', 0) for v in items)
avg_win = sum(v.get('win_rate', 0) for v in items) / len(items)

NLP_SPECS = {
    # NIFTY Baseline (10)
    "NIFTY_MACD_BULLISH_1M_ATM": "IF current time is between 09:20 AM and 03:15 PM,<br>&nbsp;&nbsp;AND IF 1-minute MACD histogram turns positive (crosses above zero),<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF NIFTY spot price is trading above both 20-EMA and 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY At-The-Money (ATM) Call Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "NIFTY_ORB_BULLISH_1M_ATM": "IF market time is at or after 09:30 AM,<br>&nbsp;&nbsp;AND IF 1-minute candle close breaks out above 09:15-09:25 AM high,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF candle volume exceeds 20-period average volume,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY At-The-Money (ATM) Call Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Wait for breakout.",
    "NIFTY_HEIKIN_ASHI_BEARISH_1M_ATM": "IF current 1-minute Heikin-Ashi candle turns red,<br>&nbsp;&nbsp;AND IF previous Heikin-Ashi candle was green,<br>&nbsp;&nbsp;&nbsp;&nbsp;OR IF NIFTY spot price is below both 20-EMA and 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY At-The-Money (ATM) Put Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "NIFTY_MACD_BEARISH_1M_ATM": "IF 1-minute MACD histogram turns negative (crosses below zero),<br>&nbsp;&nbsp;AND IF NIFTY spot price is below both 20-EMA and 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY At-The-Money (ATM) Put Option.<br>&nbsp;&nbsp;ELSE Do nothing.",
    "NIFTY_SUPPORT_BOUNCE_5M_ITM": "IF previous 5-minute candle low touched or dipped below 20-EMA,<br>&nbsp;&nbsp;AND IF current 5-minute candle closes back above 20-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF price is in a 1-Hour uptrend (above 1-Hour 50-EMA),<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY In-The-Money (~₹200 premium) Call Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "NIFTY_HEIKIN_ASHI_BULLISH_5M_ITM": "IF current 5-minute Heikin-Ashi candle is green,<br>&nbsp;&nbsp;AND IF previous Heikin-Ashi candle was also green,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF NIFTY spot price is above 1-Hour 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY In-The-Money (~₹200 premium) Call Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "NIFTY_ORB_BULLISH_5M_ITM": "IF time is at or after 09:30 AM,<br>&nbsp;&nbsp;AND IF 5-minute candle closes above 09:15-09:30 AM high,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF spot price is above 1-Hour 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY In-The-Money (~₹200 premium) Call Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Wait for breakout.",
    "NIFTY_RESISTANCE_REJECTION_5M_ITM": "IF previous 5-minute candle high touched 20-EMA resistance,<br>&nbsp;&nbsp;AND IF current 5-minute candle closes back below 20-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF price is in a 1-Hour downtrend (below 1-Hour 50-EMA),<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY In-The-Money (~₹200 premium) Put Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM": "IF current 5-minute Heikin-Ashi candle is red,<br>&nbsp;&nbsp;AND IF previous Heikin-Ashi candle was also red,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF NIFTY spot price is below 1-Hour 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY In-The-Money (~₹200 premium) Put Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "NIFTY_ORB_BEARISH_5M_ITM": "IF time is at or after 09:30 AM,<br>&nbsp;&nbsp;AND IF 5-minute candle breaks down below 09:15-09:30 AM low,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF spot price is below 1-Hour 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY In-The-Money (~₹200 premium) Put Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Wait for breakdown.",

    # NIFTY Expansion (4)
    "NIFTY_VWAP_POC_PULLBACK_CE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF spot price pulls back to test VWAP or Point-of-Control (POC),<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF bullish reversal wick forms in primary uptrend,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY In-The-Money (ITM) Call Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "NIFTY_VWAP_POC_BREAKDOWN_PE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF spot price breaks down below VWAP and Point-of-Control (POC),<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF negative volume delta accelerates,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY In-The-Money (ITM) Put Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "NIFTY_SUPERTREND_CMF_BULLISH_CE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF Supertrend (10,3) turns bullish green,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF Chaikin Money Flow (CMF 20) is positive (&gt; 0),<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY In-The-Money (ITM) Call Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "NIFTY_SUPERTREND_CMF_BEARISH_PE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF Supertrend (10,3) turns bearish red,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF Chaikin Money Flow (CMF 20) is negative (&lt; 0),<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy NIFTY In-The-Money (ITM) Put Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",

    # SENSEX Baseline (11)
    "SENSEX_MACD_BULLISH_1M_ATM": "IF SENSEX 1-minute MACD histogram crosses above zero,<br>&nbsp;&nbsp;AND IF SENSEX index is trading above 20-EMA and 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX At-The-Money (ATM) Call Option.<br>&nbsp;&nbsp;ELSE Skip trade.",
    "SENSEX_SUPPORT_BOUNCE_1M_ATM": "IF 1-minute low touches 20-EMA support on SENSEX,<br>&nbsp;&nbsp;AND IF candle closes green back above 20-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX At-The-Money (ATM) Call Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "SENSEX_HEIKIN_ASHI_BEARISH_1M_ATM": "IF SENSEX 1-minute Heikin-Ashi candle turns red,<br>&nbsp;&nbsp;AND IF previous candle was green,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX At-The-Money (ATM) Put Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "SENSEX_MACD_BEARISH_1M_ATM": "IF SENSEX 1-minute MACD crosses below zero,<br>&nbsp;&nbsp;AND IF SENSEX spot is below 20-EMA and 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX At-The-Money (ATM) Put Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "SENSEX_ORB_BEARISH_1M_ATM": "IF time is after 09:30 AM,<br>&nbsp;&nbsp;AND IF SENSEX breaks down below 09:15-09:25 AM low,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX At-The-Money (ATM) Put Option.<br>&nbsp;&nbsp;ELSE Wait for breakdown.",
    "SENSEX_SUPPORT_BOUNCE_5M_ITM": "IF 5-minute low touches 20-EMA in 1-Hour uptrend,<br>&nbsp;&nbsp;AND IF candle closes strong above 20-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX In-The-Money (~₹600 premium) Call Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "SENSEX_HEIKIN_ASHI_BULLISH_5M_ITM": "IF 2 consecutive green Heikin-Ashi candles form on 5-minute SENSEX,<br>&nbsp;&nbsp;AND IF lower wick is flat and price is above 1-Hour 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX In-The-Money (~₹600 premium) Call Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "SENSEX_ORB_BULLISH_5M_ITM": "IF time is after 09:30 AM,<br>&nbsp;&nbsp;AND IF 5-minute candle breaks out above 09:15-09:30 AM high,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX In-The-Money (~₹600 premium) Call Option.<br>&nbsp;&nbsp;ELSE Wait.",
    "SENSEX_RESISTANCE_REJECTION_5M_ITM": "IF 5-minute high touches 20-EMA resistance in 1-Hour downtrend,<br>&nbsp;&nbsp;AND IF candle rejects down,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX In-The-Money (~₹600 premium) Put Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "SENSEX_HEIKIN_ASHI_BEARISH_5M_ITM": "IF 2 consecutive red Heikin-Ashi candles form on 5-minute SENSEX,<br>&nbsp;&nbsp;AND IF upper wick is flat and price is below 1-Hour 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX In-The-Money (~₹600 premium) Put Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "SENSEX_ORB_BEARISH_5M_ITM": "IF time is after 09:30 AM,<br>&nbsp;&nbsp;AND IF 5-minute candle breaks down below 09:15-09:30 AM low,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX In-The-Money (~₹600 premium) Put Option.<br>&nbsp;&nbsp;ELSE Wait.",

    # SENSEX Expansion (4)
    "SENSEX_BB_SQUEEZE_EXPLOSION_CE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF Bollinger Band squeeze expands above Upper Band,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF breakout candle closes outside consolidation,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX In-The-Money (ITM) Call Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "SENSEX_BB_SQUEEZE_EXPLOSION_PE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF Bollinger Band squeeze expands below Lower Band,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF breakdown candle closes below consolidation,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX In-The-Money (ITM) Put Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "SENSEX_OI_SHORT_SQUEEZE_CE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF spot price crosses above highest Call Wall strike,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF Call Open Interest unwinding triggers short covering,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX At-The-Money (ATM) Call Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "SENSEX_OI_LONG_UNWINDING_PE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF spot price drops below highest Put Wall strike,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF Put Open Interest unwinding triggers panic selling,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy SENSEX At-The-Money (ATM) Put Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",

    # BANKNIFTY Baseline (11)
    "BANKNIFTY_MACD_BULLISH_1M_ATM": "IF BANKNIFTY 1-minute MACD histogram crosses above zero,<br>&nbsp;&nbsp;AND IF BANKNIFTY spot is above 20-EMA and 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY At-The-Money (ATM) Call Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "BANKNIFTY_SUPPORT_BOUNCE_1M_ATM": "IF 1-minute low touches 20-EMA support on BANKNIFTY,<br>&nbsp;&nbsp;AND IF candle closes green back above 20-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY At-The-Money (ATM) Call Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM": "IF 1-minute Heikin-Ashi red candle continuation on BANKNIFTY,<br>&nbsp;&nbsp;AND IF price is below 20-EMA and 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY At-The-Money (ATM) Put Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "BANKNIFTY_MACD_BEARISH_1M_ATM": "IF 1-minute MACD crosses below zero on BANKNIFTY,<br>&nbsp;&nbsp;AND IF BANKNIFTY spot is below 20-EMA and 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY At-The-Money (ATM) Put Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "BANKNIFTY_ORB_BEARISH_1M_ATM": "IF time is after 09:30 AM,<br>&nbsp;&nbsp;AND IF 1-minute candle breaks down below 09:15-09:25 AM low,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY At-The-Money (ATM) Put Option.<br>&nbsp;&nbsp;ELSE Wait.",
    "BANKNIFTY_SUPPORT_BOUNCE_5M_ITM": "IF 5-minute low touches 20-EMA in 1-Hour uptrend,<br>&nbsp;&nbsp;AND IF candle closes strong above 20-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY In-The-Money (~₹500 premium) Call Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "BANKNIFTY_HEIKIN_ASHI_BULLISH_5M_ITM": "IF 2 consecutive green Heikin-Ashi candles form on 5-minute BANKNIFTY,<br>&nbsp;&nbsp;AND IF lower wick is flat and price is above 1-Hour 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY In-The-Money (~₹500 premium) Call Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "BANKNIFTY_ORB_BULLISH_5M_ITM": "IF time is after 09:30 AM,<br>&nbsp;&nbsp;AND IF 5-minute candle breaks out above 09:15-09:30 AM high,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY In-The-Money (~₹500 premium) Call Option.<br>&nbsp;&nbsp;ELSE Wait.",
    "BANKNIFTY_RESISTANCE_REJECTION_5M_ITM": "IF 5-minute high touches 20-EMA resistance in 1-Hour downtrend,<br>&nbsp;&nbsp;AND IF candle rejects down,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY In-The-Money (~₹500 premium) Put Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "BANKNIFTY_HEIKIN_ASHI_BEARISH_5M_ITM": "IF 2 consecutive red Heikin-Ashi candles form on 5-minute BANKNIFTY,<br>&nbsp;&nbsp;AND IF upper wick is flat and price is below 1-Hour 50-EMA,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY In-The-Money (~₹500 premium) Put Option.<br>&nbsp;&nbsp;ELSE Skip.",
    "BANKNIFTY_ORB_BEARISH_5M_ITM": "IF time is after 09:30 AM,<br>&nbsp;&nbsp;AND IF 5-minute candle breaks down below 09:15-09:30 AM low,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY In-The-Money (~₹500 premium) Put Option.<br>&nbsp;&nbsp;ELSE Wait.",

    # BANKNIFTY Expansion (4)
    "BANKNIFTY_DUAL_SUPERTREND_BB_CE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF 15M Macro Supertrend and 5M Micro Supertrend are both green,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF price closes above Middle Bollinger Band,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY In-The-Money (ITM) Call Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "BANKNIFTY_DUAL_SUPERTREND_BB_PE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF 15M Macro Supertrend and 5M Micro Supertrend are both red,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF price closes below Middle Bollinger Band,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY In-The-Money (ITM) Put Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "BANKNIFTY_VWAP_BB_LIQUIDITY_REBOUND_CE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF 5M candle wicks below Lower Bollinger Band,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF price rebounds back above VWAP,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY In-The-Money (ITM) Call Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
    "BANKNIFTY_GAMMA_WALL_BREAKOUT_PE": "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF spot price breaks down below major Put Wall hedging level,<br>&nbsp;&nbsp;&nbsp;&nbsp;AND IF negative gamma acceleration triggers panic selling,<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;THEN Buy BANKNIFTY In-The-Money (ITM) Put Option.<br>&nbsp;&nbsp;&nbsp;&nbsp;ELSE Skip trade.",
}

def render_cards(prefix):
    cards = []
    for strat_id, s in report.items():
        if not isinstance(s, dict) or not strat_id.startswith(prefix):
            continue
        direction = s.get("direction", "CE")
        tf = "5M" if "_5M_" in strat_id else "1M"
        strike_type = "ITM" if "_ITM" in strat_id or "EXPANSION" in strat_id or "CE" in strat_id and "VWAP" in strat_id else "ATM"
        if "_ITM" in strat_id:
            strike_type = "ITM"
        elif "_ATM" in strat_id:
            strike_type = "ATM"
        else:
            strike_type = "ITM"

        is_expansion = strat_id in ["NIFTY_VWAP_POC_PULLBACK_CE", "NIFTY_VWAP_POC_BREAKDOWN_PE", "NIFTY_SUPERTREND_CMF_BULLISH_CE", "NIFTY_SUPERTREND_CMF_BEARISH_PE", "SENSEX_BB_SQUEEZE_EXPLOSION_CE", "SENSEX_BB_SQUEEZE_EXPLOSION_PE", "SENSEX_OI_SHORT_SQUEEZE_CE", "SENSEX_OI_LONG_UNWINDING_PE", "BANKNIFTY_DUAL_SUPERTREND_BB_CE", "BANKNIFTY_DUAL_SUPERTREND_BB_PE", "BANKNIFTY_VWAP_BB_LIQUIDITY_REBOUND_CE", "BANKNIFTY_GAMMA_WALL_BREAKOUT_PE"]
        idx_cls = "idx-nifty" if prefix == "NIFTY" else ("idx-sensex" if prefix == "SENSEX" else "idx-banknifty")
        card_cls = f"strat-card {'ce' if direction == 'CE' else 'pe'} {idx_cls} tf-{tf.lower()} type-{strike_type.lower()}"
        nlp_text = NLP_SPECS.get(strat_id, "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF quantitative entry conditions align,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Execute directional option trade.<br>&nbsp;&nbsp;ELSE Skip trade.")

        pnl_val = s.get("total_pnl", 0)
        pf_val = s.get("profit_factor", 0)
        pf_display = "inf" if pf_val >= 900 else f"{pf_val:.2f}"

        c_html = f'''      <!-- {strat_id} -->
      <div class="{card_cls}">
        <div>
          <div class="strat-header">
            <div>
              <div class="strat-name">{strat_id} {'★' if is_expansion else ''}</div>
              <div class="strat-badges">
                <span class="badge badge-{"ce" if direction == "CE" else "pe"}">{direction}</span>
                <span class="badge badge-{tf.lower()}">{tf}</span>
                <span class="badge badge-{strike_type.lower()}">{strike_type}</span>
                {f'<span class="badge" style="background: rgba(245, 158, 11, 0.25); color: #fbbf24;">EXPANSION</span>' if is_expansion else ''}
              </div>
            </div>
            <div class="strat-pnl"><div class="pnl-val pos">₹{pnl_val:,.2f}</div><div class="metric-sub">P&amp;L</div></div>
          </div>
          <div class="strat-stats">
            <div class="stat-item"><div class="stat-label">Trades</div><div class="stat-val">{s.get("total_trades", 0)}</div></div>
            <div class="stat-item"><div class="stat-label">Win Rate</div><div class="stat-val">{s.get("win_rate", 0):.1f}%</div></div>
            <div class="stat-item"><div class="stat-label">Profit Factor</div><div class="stat-val">{pf_display}</div></div>
          </div>
          <div class="strat-details">
            <div class="details-title">Natural Language IF-ELSE Setup</div>
            <div class="nlp-box">
              {nlp_text}
            </div>
            <div class="params-grid">
              <div class="param-row"><span>Strike Mode</span><span class="param-val">{strike_type}</span></div>
              <div class="param-row"><span>Max DD</span><span class="param-val">{s.get("max_drawdown_pct", 0):.2f}%</span></div>
            </div>
          </div>
        </div>
      </div>'''
        cards.append(c_html)
    return "\n".join(cards)

nifty_html = render_cards("NIFTY")
sensex_html = render_cards("SENSEX")
banknifty_html = render_cards("BANKNIFTY")

full_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OptionsSimulator: 44 Master Strategies Natural Language IF-ELSE Manual</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-dark: #0b0f19;
      --bg-card: #111827;
      --bg-card-hover: #1f2937;
      --border-color: #1f2937;
      --border-accent: #374151;
      --text-main: #f9fafb;
      --text-muted: #9ca3af;
      --accent-blue: #3b82f6;
      --accent-cyan: #06b6d4;
      --accent-emerald: #10b981;
      --accent-rose: #f43f5e;
      --accent-amber: #f59e0b;
      --accent-purple: #8b5cf6;
      --gradient-primary: linear-gradient(135deg, #2563eb 0%, #06b6d4 100%);
      --shadow-lg: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background-color: var(--bg-dark); color: var(--text-main); font-family: var(--font-sans); line-height: 1.6; padding-bottom: 60px; }}

    header {{
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border-color);
      position: sticky; top: 0; z-index: 100;
      padding: 16px 32px;
      display: flex; justify-content: space-between; align-items: center;
    }}

    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .brand-logo {{
      width: 38px; height: 38px;
      background: var(--gradient-primary);
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-weight: 800; font-size: 20px; color: #fff;
      box-shadow: 0 0 15px rgba(59, 130, 246, 0.4);
    }}
    .brand-title h1 {{
      font-size: 18px; font-weight: 700; letter-spacing: -0.02em;
      background: linear-gradient(90deg, #fff, #9ca3af);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .brand-title p {{ font-size: 12px; color: var(--text-muted); }}

    nav {{ display: flex; gap: 12px; }}
    .nav-btn {{
      background: #1f2937; color: var(--text-muted); border: 1px solid var(--border-accent);
      padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600;
      cursor: pointer; transition: all 0.2s ease; text-decoration: none;
    }}
    .nav-btn:hover, .nav-btn.active {{
      color: #fff; background: var(--accent-blue); border-color: var(--accent-blue);
      box-shadow: 0 0 12px rgba(59, 130, 246, 0.3);
    }}

    .container {{ max-width: 1400px; margin: 32px auto; padding: 0 24px; }}

    .hero-banner {{
      background: var(--bg-card); border: 1px solid var(--border-color);
      border-radius: 16px; padding: 28px; margin-bottom: 32px;
      box-shadow: var(--shadow-lg); position: relative; overflow: hidden;
    }}
    .hero-banner::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--gradient-primary); }}

    .hero-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 24px; }}
    .metric-card {{ background: rgba(31, 41, 55, 0.4); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 16px 20px; }}
    .metric-label {{ font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
    .metric-value {{ font-size: 26px; font-weight: 800; font-family: var(--font-mono); }}
    .metric-value.green {{ color: var(--accent-emerald); }}
    .metric-value.blue {{ color: var(--accent-cyan); }}
    .metric-value.purple {{ color: var(--accent-purple); }}
    .metric-sub {{ font-size: 12px; color: var(--text-muted); margin-top: 4px; }}

    .section-header {{ display: flex; justify-content: space-between; align-items: center; margin-top: 40px; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid var(--border-color); }}
    .section-title {{ font-size: 20px; font-weight: 700; display: flex; align-items: center; gap: 10px; }}

    .index-pill {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; letter-spacing: 0.05em; }}
    .pill-nifty {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
    .pill-sensex {{ background: rgba(139, 92, 246, 0.15); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.3); }}
    .pill-banknifty {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}

    .filter-bar {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; background: var(--bg-card); padding: 16px; border-radius: 12px; border: 1px solid var(--border-color); }}
    .filter-btn {{ background: #1f2937; color: var(--text-muted); border: 1px solid var(--border-accent); padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.15s ease; }}
    .filter-btn:hover, .filter-btn.active {{ background: var(--accent-blue); color: #fff; border-color: var(--accent-blue); }}

    .strategy-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(440px, 1fr)); gap: 24px; margin-bottom: 48px; }}
    .strat-card {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 24px; box-shadow: var(--shadow-lg); transition: transform 0.2s ease, border-color 0.2s ease; position: relative; display: flex; flex-direction: column; justify-content: space-between; }}
    .strat-card:hover {{ transform: translateY(-4px); border-color: var(--border-accent); }}
    .strat-card.ce {{ border-left: 4px solid var(--accent-emerald); }}
    .strat-card.pe {{ border-left: 4px solid var(--accent-rose); }}

    .strat-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }}
    .strat-name {{ font-size: 15px; font-weight: 700; font-family: var(--font-mono); color: #fff; margin-bottom: 4px; }}
    .strat-badges {{ display: flex; gap: 6px; margin-top: 4px; flex-wrap: wrap; }}

    .badge {{ font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; font-family: var(--font-mono); }}
    .badge-ce {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
    .badge-pe {{ background: rgba(244, 63, 94, 0.2); color: #f87171; }}
    .badge-1m {{ background: rgba(6, 182, 212, 0.2); color: #22d3ee; }}
    .badge-5m {{ background: rgba(168, 85, 247, 0.2); color: #c084fc; }}
    .badge-atm {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; }}
    .badge-itm {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; }}

    .strat-pnl {{ text-align: right; }}
    .pnl-val {{ font-size: 18px; font-weight: 800; font-family: var(--font-mono); }}
    .pnl-val.pos {{ color: var(--accent-emerald); }}

    .strat-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; background: rgba(31, 41, 55, 0.5); border-radius: 8px; padding: 10px; margin-bottom: 16px; }}
    .stat-item {{ text-align: center; }}
    .stat-label {{ font-size: 10px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }}
    .stat-val {{ font-size: 14px; font-weight: 700; font-family: var(--font-mono); }}

    .strat-details {{ border-top: 1px solid var(--border-color); padding-top: 14px; margin-top: 8px; }}
    .details-title {{ font-size: 12px; font-weight: 700; color: var(--accent-cyan); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }}

    .nlp-box {{
      background: #090d16;
      border: 1px solid #1f2937;
      border-radius: 8px;
      padding: 14px;
      font-size: 12px;
      color: #e5e7eb;
      line-height: 1.6;
      margin-bottom: 12px;
    }}
    .nlp-if {{ color: #f472b6; font-weight: 700; }}
    .nlp-and {{ color: #60a5fa; font-weight: 700; }}
    .nlp-then {{ color: #34d399; font-weight: 700; }}
    .nlp-else {{ color: #fbbf24; font-weight: 700; }}

    .params-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 11px; color: var(--text-muted); }}
    .param-row {{ display: flex; justify-content: space-between; background: rgba(31, 41, 55, 0.3); padding: 4px 8px; border-radius: 4px; }}
    .param-val {{ font-weight: 600; color: var(--text-main); font-family: var(--font-mono); }}

    footer {{ text-align: center; padding: 24px; color: var(--text-muted); font-size: 12px; border-top: 1px solid var(--border-color); margin-top: 40px; }}
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="brand-logo">Ω</div>
      <div class="brand-title">
        <h1>OptionsSimulator 44-Strategy Master Manual</h1>
        <p>Plain English Natural Language IF-ELSE Conditions &amp; Audit (14 NIFTY | 15 SENSEX | 15 BANKNIFTY)</p>
      </div>
    </div>
    <nav>
      <a href="#summary" class="nav-btn active">Overview</a>
      <a href="#nifty" class="nav-btn">NIFTY (14)</a>
      <a href="#sensex" class="nav-btn">SENSEX (15)</a>
      <a href="#banknifty" class="nav-btn">BANKNIFTY (15)</a>
    </nav>
  </header>

  <div class="container">

    <div class="hero-banner" id="summary">
      <div class="hero-grid">
        <div class="metric-card">
          <div class="metric-label">Total Master Strategies</div>
          <div class="metric-value blue">44 Strategies</div>
          <div class="metric-sub">NIFTY (14) | SENSEX (15) | BANKNIFTY (15)</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Combined Net P&amp;L (1-Year)</div>
          <div class="metric-value green">₹{tot_pnl:,.2f}</div>
          <div class="metric-sub">Across {tot_trades:,} total execution trades</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Overall Win Rate Average</div>
          <div class="metric-value purple">{avg_win:.1f}%</div>
          <div class="metric-sub">09:25 AM Cutoff Gate Enforced</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Execution Timeframes</div>
          <div class="metric-value">1M &amp; 5M</div>
          <div class="metric-sub">ATM Baseline &amp; ITM Expansion Suite</div>
        </div>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="filter-bar">
      <button class="filter-btn active" onclick="filterGrid('all')">Show All 44</button>
      <button class="filter-btn" onclick="filterGrid('nifty')">NIFTY (14)</button>
      <button class="filter-btn" onclick="filterGrid('sensex')">SENSEX (15)</button>
      <button class="filter-btn" onclick="filterGrid('banknifty')">BANKNIFTY (15)</button>
      <button class="filter-btn" onclick="filterGrid('ce')">CE (Bullish)</button>
      <button class="filter-btn" onclick="filterGrid('pe')">PE (Bearish)</button>
      <button class="filter-btn" onclick="filterGrid('1m')">1M Micro-Scalps</button>
      <button class="filter-btn" onclick="filterGrid('5m')">5M High-Conviction</button>
    </div>

    <!-- NIFTY SECTION -->
    <div class="section-header" id="nifty">
      <div class="section-title">
        <span>NIFTY 50 Strategy Suite</span>
        <span class="index-pill pill-nifty">14 STRATEGIES (Lot Size: 65, Step: 50)</span>
      </div>
    </div>

    <div class="strategy-grid">
{nifty_html}
    </div>

    <!-- SENSEX SECTION -->
    <div class="section-header" id="sensex">
      <div class="section-title">
        <span>BSE SENSEX Strategy Suite</span>
        <span class="index-pill pill-sensex">15 STRATEGIES (Lot Size: 20, Step: 100)</span>
      </div>
    </div>

    <div class="strategy-grid">
{sensex_html}
    </div>

    <!-- BANKNIFTY SECTION -->
    <div class="section-header" id="banknifty">
      <div class="section-title">
        <span>BANKNIFTY Strategy Suite</span>
        <span class="index-pill pill-banknifty">15 STRATEGIES (Lot Size: 30, Step: 100)</span>
      </div>
    </div>

    <div class="strategy-grid">
{banknifty_html}
    </div>

  </div>

  <footer>
    <p>OptionsSimulator 44-Strategy Natural Language IF-ELSE Master Manual Artifact</p>
  </footer>

  <script>
    function filterGrid(type) {{
      const buttons = document.querySelectorAll('.filter-btn');
      buttons.forEach(btn => btn.classList.remove('active'));
      event.target.classList.add('active');

      const cards = document.querySelectorAll('.strat-card');
      cards.forEach(card => {{
        if (type === 'all') {{
          card.style.display = 'flex';
          return;
        }}

        let show = false;
        if (type === 'nifty' && card.classList.contains('idx-nifty')) show = true;
        if (type === 'sensex' && card.classList.contains('idx-sensex')) show = true;
        if (type === 'banknifty' && card.classList.contains('idx-banknifty')) show = true;
        if (type === 'ce' && card.classList.contains('ce')) show = true;
        if (type === 'pe' && card.classList.contains('pe')) show = true;
        if (type === '1m' && card.classList.contains('tf-1m')) show = true;
        if (type === '5m' && card.classList.contains('tf-5m')) show = true;

        card.style.display = show ? 'flex' : 'none';
      }});
    }}
  </script>
</body>
</html>'''

out_path = Path('c:/Users/parth/.gemini/antigravity-ide/brain/b14897f6-6116-4bff-ad62-8594b2291610/master_44_strategies_report.html')
out_path.write_text(full_html, encoding='utf-8')
print("Successfully generated master_44_strategies_report.html artifact!")
