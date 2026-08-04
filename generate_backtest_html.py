"""
Renders data/backtest_results/report.json + daily_report.json + capital_requirements.json
(produced by `python main.py`) into a single self-contained HTML report — no server, no build
step, just open it in a browser.
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
REPORT_JSON = PROJECT_ROOT / "data" / "backtest_results" / "report.json"
DAILY_JSON = PROJECT_ROOT / "data" / "backtest_results" / "daily_report.json"
CAPITAL_JSON = PROJECT_ROOT / "data" / "backtest_results" / "capital_requirements.json"
OUTPUT_HTML = PROJECT_ROOT / "data" / "backtest_results" / "report.html"


def _pnl_class(value: float) -> str:
    return "pos" if value > 0 else "neg" if value < 0 else "flat"


def _ranked_rows(strategies: dict, direction: str, top_n: int = 3) -> str:
    ranked = sorted(
        (s for s in strategies.values() if s["direction"] == direction),
        key=lambda r: (r["profit_factor"], r["win_rate"]), reverse=True,
    )
    rows = []
    for i, r in enumerate(ranked, 1):
        deploy = i <= top_n and r["total_trades"] > 0
        rows.append(f"""
        <tr>
          <td>{i}</td>
          <td>{r['strategy']}</td>
          <td>{r['total_trades']}</td>
          <td>{r['win_rate']}%</td>
          <td>{r['profit_factor']}</td>
          <td class="{_pnl_class(r['total_pnl'])}">Rs.{r['total_pnl']:,.2f}</td>
          <td>{r['max_drawdown_pct']}%</td>
          <td>{'<span class="badge">DEPLOY</span>' if deploy else '-'}</td>
        </tr>""")
    return "".join(rows)


def _hedge_rows(strategies: dict) -> str:
    hedge = [s for s in strategies.values() if s["direction"] == "HEDGE"]
    rows = []
    for r in hedge:
        rows.append(f"""
        <tr>
          <td>{r['strategy']}</td>
          <td>{r['total_trades']}</td>
          <td>{r['win_rate']}%</td>
          <td>{r['profit_factor']}</td>
          <td class="{_pnl_class(r['total_pnl'])}">Rs.{r['total_pnl']:,.2f}</td>
          <td>{r['max_drawdown_pct']}%</td>
        </tr>""")
    return "".join(rows)


def _capital_rows(capital: dict) -> str:
    rows = []
    for name, info in capital.items():
        rows.append(f"""
        <tr>
          <td>{name}</td>
          <td>Rs.{info['avg_trade_risk']:,.2f}</td>
          <td>Rs.{info['max_historical_drawdown']:,.2f}</td>
          <td><strong>Rs.{info['recommended_capital']:,.0f}</strong></td>
        </tr>""")
    return "".join(rows)


def _daily_table(strategy: str, days: list) -> str:
    if not days:
        return f"""
        <details class="strategy">
          <summary>{strategy} <span class="muted">(no closed trades in this period)</span></summary>
        </details>"""

    rows = "".join(f"""
        <tr>
          <td>{d['date']}</td>
          <td>{d['trades']}</td>
          <td>{d['wins']}</td>
          <td>{d['losses']}</td>
          <td>{d['win_rate']}%</td>
          <td class="{_pnl_class(d['pnl'])}">Rs.{d['pnl']:,.2f}</td>
          <td class="{_pnl_class(d['cumulative_pnl'])}">Rs.{d['cumulative_pnl']:,.2f}</td>
        </tr>""" for d in days)

    return f"""
    <details class="strategy">
      <summary>{strategy} <span class="muted">({len(days)} trading days)</span></summary>
      <table>
        <thead><tr><th>Date</th><th>Trades</th><th>Wins</th><th>Losses</th><th>Win %</th><th>P&amp;L</th><th>Cumulative P&amp;L</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </details>"""


def generate() -> Path:
    strategies = json.loads(REPORT_JSON.read_text())
    selected = strategies.pop("_selected", {"CE": [], "PE": []})
    daily = json.loads(DAILY_JSON.read_text()) if DAILY_JSON.exists() else {}
    capital = json.loads(CAPITAL_JSON.read_text()) if CAPITAL_JSON.exists() else {}

    deployed_names = set(selected.get("CE", [])) | set(selected.get("PE", []))
    deployed_pnl = sum(strategies[n]["total_pnl"] for n in deployed_names if n in strategies)
    deployed_win_rates = [strategies[n]["win_rate"] for n in deployed_names if n in strategies]
    avg_win_rate = round(sum(deployed_win_rates) / len(deployed_win_rates), 1) if deployed_win_rates else 0.0

    all_dates = sorted({d["date"] for days in daily.values() for d in days})
    date_range = f"{all_dates[0]} to {all_dates[-1]}" if all_dates else "no closed trades"

    ce_ranked_names = sorted(
        (s for s in strategies.values() if s["direction"] == "CE"),
        key=lambda r: (r["profit_factor"], r["win_rate"]), reverse=True,
    )
    pe_ranked_names = sorted(
        (s for s in strategies.values() if s["direction"] == "PE"),
        key=lambda r: (r["profit_factor"], r["win_rate"]), reverse=True,
    )
    hedge_names = [s for s in strategies.values() if s["direction"] == "HEDGE"]
    ordered_names = ([r["strategy"] for r in ce_ranked_names] + [r["strategy"] for r in pe_ranked_names]
                      + [r["strategy"] for r in hedge_names])
    daily_sections = "".join(_daily_table(name, daily.get(name, [])) for name in ordered_names)

    total_strategies = len(strategies)
    directional_count = total_strategies - len(hedge_names)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OptionsSimulator — Backtest Report</title>
<style>
  :root {{
    --bg: #0f1117; --card: #171a24; --border: #2a2e3d; --text: #e6e8ef; --muted: #8b90a3;
    --pos: #3ddc84; --neg: #ff6b6b; --accent: #5b8cff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px; background: var(--bg); color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
  }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .subtitle {{ color: var(--muted); margin: 0 0 28px; font-size: 14px; }}
  .cards {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
  .card {{
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 16px 20px; min-width: 180px;
  }}
  .card .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
  .card .value {{ font-size: 22px; font-weight: 600; margin-top: 4px; }}
  h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); margin: 32px 0 10px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 500; font-size: 12px; text-transform: uppercase; }}
  tr:hover td {{ background: rgba(255,255,255,0.02); }}
  .pos {{ color: var(--pos); }}
  .neg {{ color: var(--neg); }}
  .flat {{ color: var(--muted); }}
  .badge {{
    background: var(--accent); color: white; font-size: 11px; font-weight: 600;
    padding: 2px 8px; border-radius: 999px;
  }}
  .rank-table {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 4px 12px; }}
  details.strategy {{
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 10px 16px; margin-bottom: 10px;
  }}
  details.strategy summary {{ cursor: pointer; font-weight: 600; font-size: 14px; padding: 4px 0; }}
  details.strategy table {{ margin-top: 10px; }}
  .muted {{ color: var(--muted); font-weight: 400; font-size: 12px; }}
  .note {{ color: var(--muted); font-size: 12px; margin: 8px 0 0; }}
</style>
</head>
<body>
  <h1>OptionsSimulator — Backtest Report</h1>
  <p class="subtitle">NIFTY options, {directional_count} directional strategies + {len(hedge_names)} expiry-day hedge · data range: {date_range}</p>

  <div class="cards">
    <div class="card"><div class="label">Deployed strategies</div><div class="value">{len(deployed_names)}</div></div>
    <div class="card"><div class="label">Deployed P&amp;L</div><div class="value {_pnl_class(deployed_pnl)}">Rs.{deployed_pnl:,.2f}</div></div>
    <div class="card"><div class="label">Avg win rate</div><div class="value">{avg_win_rate}%</div></div>
  </div>

  <h2>Bullish (CE) Strategies</h2>
  <div class="rank-table">
    <table>
      <thead><tr><th>Rank</th><th>Strategy</th><th>Trades</th><th>Win %</th><th>PF</th><th>P&amp;L</th><th>Max DD%</th><th>Status</th></tr></thead>
      <tbody>{_ranked_rows(strategies, "CE")}</tbody>
    </table>
  </div>

  <h2>Bearish (PE) Strategies</h2>
  <div class="rank-table">
    <table>
      <thead><tr><th>Rank</th><th>Strategy</th><th>Trades</th><th>Win %</th><th>PF</th><th>P&amp;L</th><th>Max DD%</th><th>Status</th></tr></thead>
      <tbody>{_ranked_rows(strategies, "PE")}</tbody>
    </table>
  </div>

  <h2>Hedge Strategies (expiry day only)</h2>
  <div class="rank-table">
    <table>
      <thead><tr><th>Strategy</th><th>Trades</th><th>Win %</th><th>PF</th><th>P&amp;L</th><th>Max DD%</th></tr></thead>
      <tbody>{_hedge_rows(strategies)}</tbody>
    </table>
  </div>
  <p class="note">Not ranked against directional strategies (different risk profile: defined-risk premium selling, only active on Thursdays).</p>

  <h2>Required Capital Per Strategy</h2>
  <div class="rank-table">
    <table>
      <thead><tr><th>Strategy</th><th>Avg trade risk</th><th>Max historical drawdown</th><th>Recommended capital</th></tr></thead>
      <tbody>{_capital_rows(capital)}</tbody>
    </table>
  </div>
  <p class="note">Recommended capital = avg trade risk &times; 1.3 (30% buffer over what a single lot costs), rounded up to the nearest Rs.1,000 &mdash; reused day after day, not spent once per trade. Max historical drawdown is shown for context, not used to size this figure &mdash; that's what the circuit breaker is for.</p>

  <h2>Day-by-Day, Per Strategy</h2>
  {daily_sections}
</body>
</html>"""

    OUTPUT_HTML.write_text(html, encoding="utf-8")
    return OUTPUT_HTML


if __name__ == "__main__":
    path = generate()
    print(f"Backtest HTML report written to {path}")
