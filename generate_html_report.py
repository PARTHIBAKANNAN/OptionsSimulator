"""
Builds a single self-contained HTML report from the 2-per-day-per-strategy unrestricted replay
(replay_trades_2perday.csv / replay_signal_log_2perday.csv), for manual trade-by-trade review.
"""
import json
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data" / "market_analysis"
OUT_PATH = PROJECT_ROOT / "data" / "market_analysis" / "week1_2perday_report.html"


def index_of(symbol: str) -> str:
    if symbol.startswith("BANKNIFTY"):
        return "BANKNIFTY"
    if symbol.startswith("SENSEX"):
        return "SENSEX"
    return "NIFTY"


def main():
    trades = pd.read_csv(DATA_DIR / "replay_trades_2perday.csv")
    trades["entry_time"] = pd.to_datetime(trades["entry_time"])
    trades["exit_time"] = pd.to_datetime(trades["exit_time"])
    trades["entry_date"] = trades["entry_time"].dt.strftime("%Y-%m-%d (%a)")
    trades["entry_time_str"] = trades["entry_time"].dt.strftime("%H:%M:%S")
    trades["exit_time_str"] = trades["exit_time"].dt.strftime("%H:%M:%S")
    trades["hold_min"] = ((trades["exit_time"] - trades["entry_time"]).dt.total_seconds() / 60).round(1)
    trades["index"] = trades["symbol"].apply(index_of)
    trades["direction"] = trades["symbol"].apply(lambda s: "CE" if s.endswith("CE") else "PE")
    trades["is_win"] = trades["pnl"] > 0
    trades["pnl"] = trades["pnl"].round(2)
    trades["entry_price"] = trades["entry_price"].round(2)
    trades["exit_price"] = trades["exit_price"].round(2)
    trades = trades.sort_values("entry_time").reset_index(drop=True)

    # ---- summary stats ----
    total_trades = len(trades)
    wins = int(trades["is_win"].sum())
    losses = total_trades - wins
    win_rate = round(wins / total_trades * 100, 1) if total_trades else 0.0
    total_pnl = round(trades["pnl"].sum(), 2)

    by_day = trades.groupby("entry_date").agg(trades=("pnl", "count"), wins=("is_win", "sum"), pnl=("pnl", "sum")).reset_index()
    by_day["win_rate"] = (by_day["wins"] / by_day["trades"] * 100).round(1)
    by_day["pnl"] = by_day["pnl"].round(2)

    by_strategy = trades.groupby("strategy").agg(trades=("pnl", "count"), wins=("is_win", "sum"), pnl=("pnl", "sum")).reset_index()
    by_strategy["win_rate"] = (by_strategy["wins"] / by_strategy["trades"] * 100).round(1)
    by_strategy["pnl"] = by_strategy["pnl"].round(2)
    by_strategy = by_strategy.sort_values("pnl", ascending=False)

    all_44 = set()
    from src.strategies.engine import create_nifty_strategies, create_sensex_strategies, create_banknifty_strategies
    for factory in (create_nifty_strategies, create_sensex_strategies, create_banknifty_strategies):
        all_44.update(s.name for s in factory())
    zero_signal = sorted(all_44 - set(trades["strategy"].unique()))

    trade_records = trades[[
        "entry_date", "entry_time_str", "exit_time_str", "hold_min", "index", "direction", "strategy",
        "symbol", "entry_price", "exit_price", "pnl", "exit_reason", "is_win",
    ]].to_dict(orient="records")

    strategy_records = by_strategy.to_dict(orient="records")
    day_records = by_day.to_dict(orient="records")

    html = HTML_TEMPLATE.format(
        total_trades=total_trades, wins=wins, losses=losses, win_rate=win_rate, total_pnl=total_pnl,
        pnl_class="pos" if total_pnl > 0 else ("neg" if total_pnl < 0 else ""),
        trades_json=json.dumps(trade_records),
        strategy_json=json.dumps(strategy_records),
        day_json=json.dumps(day_records),
        zero_signal_json=json.dumps(zero_signal),
    )
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Report written to {OUT_PATH}")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Week 1 Replay Report — 2 trades/day/strategy, no concurrency</title>
<style>
  :root {{
    --bg: #0f1420; --panel: #161d2e; --panel2: #1c2438; --border: #2a3350;
    --text: #e6e9f0; --muted: #8a92ab; --green: #3ddc97; --red: #ff6b6b;
    --accent: #5b8cff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px; background: var(--bg); color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif; font-size: 14px;
  }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  h2 {{ font-size: 15px; margin: 28px 0 10px; color: var(--accent); }}
  .subtitle {{ color: var(--muted); margin-bottom: 20px; }}
  .kpi-row {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }}
  .kpi {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px 18px; min-width: 140px;
  }}
  .kpi .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
  .kpi .value {{ font-size: 22px; font-weight: 600; margin-top: 4px; }}
  .pos {{ color: var(--green); }}
  .neg {{ color: var(--red); }}
  table {{
    width: 100%; border-collapse: collapse; background: var(--panel);
    border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
  }}
  th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  th {{
    background: var(--panel2); color: var(--muted); font-weight: 600; font-size: 12px;
    text-transform: uppercase; letter-spacing: .03em; cursor: pointer; position: sticky; top: 0;
  }}
  th:hover {{ color: var(--accent); }}
  tr:hover td {{ background: #1a2236; }}
  .badge {{ padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
  .badge.CE {{ background: rgba(61,220,151,.15); color: var(--green); }}
  .badge.PE {{ background: rgba(255,107,107,.15); color: var(--red); }}
  .exit-badge {{ padding: 2px 8px; border-radius: 6px; font-size: 11px; }}
  .exit-STOP_LOSS {{ background: rgba(255,107,107,.15); color: var(--red); }}
  .exit-TAKE_PROFIT {{ background: rgba(61,220,151,.18); color: var(--green); }}
  .exit-TRAILING_STOP {{ background: rgba(91,140,255,.15); color: var(--accent); }}
  .exit-TIME_EXIT {{ background: rgba(255,193,80,.15); color: #ffc150; }}
  .exit-EOD_SQUARE_OFF {{ background: rgba(138,146,171,.15); color: var(--muted); }}
  .controls {{ display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; align-items: center; }}
  .controls select, .controls input {{
    background: var(--panel2); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 10px; font-size: 13px;
  }}
  .table-wrap {{ max-height: 640px; overflow: auto; border-radius: 10px; }}
  .zero-list {{ color: var(--muted); font-size: 13px; line-height: 1.6; }}
  .note {{ color: var(--muted); font-size: 12px; margin-top: 6px; }}
</style>
</head>
<body>

<h1>Week 1 Replay — Aug 31 to Sep 2, 2026</h1>
<div class="subtitle">All 44 strategies, real Fyers 1-min candles, current (bug-fixed) code &mdash; capped at 2 entries/day/strategy, never concurrent (a strategy's next signal is skipped until its current position closes). Black-Scholes pricing (no live option-chain history available offline).</div>

<div class="kpi-row">
  <div class="kpi"><div class="label">Total Trades</div><div class="value">{total_trades}</div></div>
  <div class="kpi"><div class="label">Wins / Losses</div><div class="value">{wins} / {losses}</div></div>
  <div class="kpi"><div class="label">Win Rate</div><div class="value">{win_rate}%</div></div>
  <div class="kpi"><div class="label">Net P&amp;L</div><div class="value {pnl_class}">₹{total_pnl:,.2f}</div></div>
</div>

<h2>By Day</h2>
<table id="dayTable"><thead><tr><th>Date</th><th>Trades</th><th>Wins</th><th>Win Rate</th><th>Net P&amp;L</th></tr></thead><tbody></tbody></table>

<h2>By Strategy (sorted by P&amp;L)</h2>
<div class="table-wrap">
<table id="strategyTable"><thead><tr>
  <th data-key="strategy">Strategy</th><th data-key="trades">Trades</th><th data-key="wins">Wins</th>
  <th data-key="win_rate">Win Rate</th><th data-key="pnl">Net P&amp;L</th>
</tr></thead><tbody></tbody></table>
</div>

<h2>Strategies with Zero Signals This Window</h2>
<div class="zero-list" id="zeroList"></div>

<h2>Full Trade Log</h2>
<div class="controls">
  <select id="filterIndex"><option value="">All Indices</option><option>NIFTY</option><option>SENSEX</option><option>BANKNIFTY</option></select>
  <select id="filterDay"><option value="">All Days</option></select>
  <select id="filterExit"><option value="">All Exit Reasons</option></select>
  <input id="filterStrategy" placeholder="Filter strategy name...">
  <span class="note" id="rowCount"></span>
</div>
<div class="table-wrap">
<table id="tradeTable">
<thead><tr>
  <th data-key="entry_date">Date</th>
  <th data-key="entry_time_str">Entry Time</th>
  <th data-key="exit_time_str">Exit Time</th>
  <th data-key="hold_min">Hold (min)</th>
  <th data-key="index">Index</th>
  <th data-key="direction">Dir</th>
  <th data-key="strategy">Strategy</th>
  <th data-key="symbol">Symbol</th>
  <th data-key="entry_price">Entry ₹</th>
  <th data-key="exit_price">Exit ₹</th>
  <th data-key="pnl">P&amp;L ₹</th>
  <th data-key="exit_reason">Exit Reason</th>
</tr></thead>
<tbody id="tradeBody"></tbody>
</table>
</div>

<script>
const TRADES = {trades_json};
const STRATEGIES = {strategy_json};
const DAYS = {day_json};
const ZERO_SIGNAL = {zero_signal_json};

function fmtPnl(v) {{
  const cls = v > 0 ? 'pos' : (v < 0 ? 'neg' : '');
  const sign = v > 0 ? '+' : '';
  return `<span class="${{cls}}">${{sign}}${{v.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}})}}</span>`;
}}

function renderDayTable() {{
  const tbody = document.querySelector('#dayTable tbody');
  tbody.innerHTML = DAYS.map(d => `<tr>
    <td>${{d.entry_date}}</td><td>${{d.trades}}</td><td>${{d.wins}}</td><td>${{d.win_rate}}%</td><td>${{fmtPnl(d.pnl)}}</td>
  </tr>`).join('');
}}

function renderStrategyTable() {{
  const tbody = document.querySelector('#strategyTable tbody');
  tbody.innerHTML = STRATEGIES.map(s => `<tr>
    <td>${{s.strategy}}</td><td>${{s.trades}}</td><td>${{s.wins}}</td><td>${{s.win_rate}}%</td><td>${{fmtPnl(s.pnl)}}</td>
  </tr>`).join('');
}}

function renderZeroList() {{
  document.getElementById('zeroList').innerHTML = ZERO_SIGNAL.length
    ? ZERO_SIGNAL.join(' &nbsp;•&nbsp; ')
    : '(none — every strategy produced at least one signal)';
}}

let sortKey = 'entry_date', sortDir = 1;

function applyFiltersAndRender() {{
  const idx = document.getElementById('filterIndex').value;
  const day = document.getElementById('filterDay').value;
  const exitReason = document.getElementById('filterExit').value;
  const stratFilter = document.getElementById('filterStrategy').value.toUpperCase();

  let rows = TRADES.filter(t =>
    (!idx || t.index === idx) &&
    (!day || t.entry_date === day) &&
    (!exitReason || t.exit_reason === exitReason) &&
    (!stratFilter || t.strategy.toUpperCase().includes(stratFilter))
  );

  rows.sort((a, b) => {{
    let av = a[sortKey], bv = b[sortKey];
    if (typeof av === 'string') {{ av = av.toLowerCase(); bv = bv.toLowerCase(); }}
    if (av < bv) return -1 * sortDir;
    if (av > bv) return 1 * sortDir;
    return 0;
  }});

  document.getElementById('rowCount').textContent = `${{rows.length}} trades shown`;
  document.getElementById('tradeBody').innerHTML = rows.map(t => `<tr>
    <td>${{t.entry_date}}</td>
    <td>${{t.entry_time_str}}</td>
    <td>${{t.exit_time_str}}</td>
    <td>${{t.hold_min}}</td>
    <td>${{t.index}}</td>
    <td><span class="badge ${{t.direction}}">${{t.direction}}</span></td>
    <td>${{t.strategy}}</td>
    <td>${{t.symbol}}</td>
    <td>${{t.entry_price.toFixed(2)}}</td>
    <td>${{t.exit_price.toFixed(2)}}</td>
    <td>${{fmtPnl(t.pnl)}}</td>
    <td><span class="exit-badge exit-${{t.exit_reason}}">${{t.exit_reason}}</span></td>
  </tr>`).join('');
}}

function populateFilterOptions() {{
  const daySel = document.getElementById('filterDay');
  [...new Set(TRADES.map(t => t.entry_date))].sort().forEach(d => {{
    const o = document.createElement('option'); o.value = d; o.textContent = d; daySel.appendChild(o);
  }});
  const exitSel = document.getElementById('filterExit');
  [...new Set(TRADES.map(t => t.exit_reason))].sort().forEach(r => {{
    const o = document.createElement('option'); o.value = r; o.textContent = r; exitSel.appendChild(o);
  }});
}}

document.querySelectorAll('#tradeTable th').forEach(th => {{
  th.addEventListener('click', () => {{
    const key = th.dataset.key;
    if (sortKey === key) sortDir *= -1; else {{ sortKey = key; sortDir = 1; }}
    applyFiltersAndRender();
  }});
}});

['filterIndex', 'filterDay', 'filterExit', 'filterStrategy'].forEach(id =>
  document.getElementById(id).addEventListener('input', applyFiltersAndRender));

renderDayTable();
renderStrategyTable();
renderZeroList();
populateFilterOptions();
applyFiltersAndRender();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
