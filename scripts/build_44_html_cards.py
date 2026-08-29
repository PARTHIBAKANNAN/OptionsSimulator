import json
from pathlib import Path

with open('data/backtest_results/report.json') as f:
    report = json.load(f)

# Qualitative NLP IF-ELSE conditions for all 44 strategies (zero code leaks, clean executive NLP)
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

nifty_cards = []
sensex_cards = []
banknifty_cards = []

for strat_id, s in report.items():
    if not isinstance(s, dict):
        continue
    direction = s.get("direction", "CE")
    tf = "5M" if "_5M_" in strat_id else "1M"
    strike_type = "ITM" if "_ITM" in strat_id or "EXPANSION" in strat_id else "ATM"
    is_expansion = strat_id in ["NIFTY_VWAP_POC_PULLBACK_CE", "NIFTY_VWAP_POC_BREAKDOWN_PE", "NIFTY_SUPERTREND_CMF_BULLISH_CE", "NIFTY_SUPERTREND_CMF_BEARISH_PE", "SENSEX_BB_SQUEEZE_EXPLOSION_CE", "SENSEX_BB_SQUEEZE_EXPLOSION_PE", "SENSEX_OI_SHORT_SQUEEZE_CE", "SENSEX_OI_LONG_UNWINDING_PE", "BANKNIFTY_DUAL_SUPERTREND_BB_CE", "BANKNIFTY_DUAL_SUPERTREND_BB_PE", "BANKNIFTY_VWAP_BB_LIQUIDITY_REBOUND_CE", "BANKNIFTY_GAMMA_WALL_BREAKOUT_PE"]
    
    idx_cls = "idx-nifty" if strat_id.startswith("NIFTY") else ("idx-sensex" if strat_id.startswith("SENSEX") else "idx-banknifty")
    card_cls = f"strat-card {'ce' if direction == 'CE' else 'pe'} {idx_cls} tf-{tf.lower()} type-{strike_type.lower()}"
    nlp_text = NLP_SPECS.get(strat_id, "IF time is at or after 09:25 AM cutoff,<br>&nbsp;&nbsp;AND IF quantitative entry conditions align,<br>&nbsp;&nbsp;&nbsp;&nbsp;THEN Execute directional option trade.<br>&nbsp;&nbsp;ELSE Skip trade.")

    pnl_val = s.get("total_pnl", 0)
    pf_val = s.get("profit_factor", 0)
    pf_display = "inf" if pf_val >= 900 else f"{pf_val:.2f}"

    card_html = f'''      <!-- {strat_id} -->
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

    if strat_id.startswith("NIFTY"):
        nifty_cards.append(card_html)
    elif strat_id.startswith("SENSEX"):
        sensex_cards.append(card_html)
    else:
        banknifty_cards.append(card_html)

print("NIFTY Cards:", len(nifty_cards))
print("SENSEX Cards:", len(sensex_cards))
print("BANKNIFTY Cards:", len(banknifty_cards))
