import json
from pathlib import Path

report_path = Path("data/backtest_results/report.json")
with open(report_path) as f:
    data = json.load(f)

data_json = json.dumps(data, separators=(',', ':'))

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>365-Day Backtest Report - 44 Strategies</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0a0e27; --panel: #141829; --border: #2d3561;
    --text: #e8ecf1; --muted: #8a92a8; --green: #22c55e; --red: #ef4444;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg); color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
    padding: 24px; line-height: 1.6;
  }}
  .container {{ max-width: 1400px; margin: 0 auto; }}
  h1 {{ font-size: 28px; margin-bottom: 8px; color: #60a5fa; }}
  .subtitle {{ color: var(--muted); font-size: 13px; margin-bottom: 24px; }}
  h2 {{ font-size: 16px; margin: 24px 0 12px; color: #60a5fa; }}

  .kpi-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px; margin-bottom: 24px;
  }}
  .kpi {{
    background: var(--panel); border: 1px solid var(--border);
    padding: 16px; border-radius: 8px;
  }}
  .kpi-label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; margin-bottom: 6px; }}
  .kpi-value {{ font-size: 22px; font-weight: 700; }}
  .pos {{ color: var(--green); }}
  .neg {{ color: var(--red); }}

  .chart-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 16px; margin-bottom: 24px;
  }}
  .chart-container {{
    background: var(--panel); border: 1px solid var(--border);
    padding: 16px; border-radius: 8px;
  }}

  .controls {{
    display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap;
  }}
  input, select {{
    background: #1a1f3a; border: 1px solid var(--border);
    color: var(--text); padding: 8px 10px; border-radius: 6px; font-size: 12px;
  }}

  table {{
    width: 100%; border-collapse: collapse;
    background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  }}
  th {{
    background: #1a1f3a; padding: 10px; text-align: left;
    font-size: 11px; font-weight: 600; color: var(--muted); cursor: pointer;
  }}
  td {{ padding: 10px; border-bottom: 1px solid var(--border); font-size: 12px; }}
  tbody tr:hover {{ background: rgba(96,165,250,0.05); }}

  .badge {{
    display: inline-block; padding: 3px 6px; border-radius: 3px;
    font-size: 10px; font-weight: 600;
  }}
  .badge-ce {{ background: rgba(34,197,94,0.15); color: var(--green); }}
  .badge-pe {{ background: rgba(239,68,68,0.15); color: var(--red); }}
</style>
</head>
<body>

<div class="container">
  <h1>365-Day Backtest Report</h1>
  <p class="subtitle">Fixed Code | Real Indicators | Per-Index Routing | Sep 2, 2026 11:50 AM</p>

  <div class="kpi-grid" id="kpis"></div>

  <div class="chart-grid">
    <div class="chart-container">
      <h3 style="font-size:13px; margin-bottom:12px;">Win Rate by Index</h3>
      <canvas id="chart1"></canvas>
    </div>
    <div class="chart-container">
      <h3 style="font-size:13px; margin-bottom:12px;">Total P&L by Index</h3>
      <canvas id="chart2"></canvas>
    </div>
    <div class="chart-container">
      <h3 style="font-size:13px; margin-bottom:12px;">Top 10 Strategies</h3>
      <canvas id="chart3"></canvas>
    </div>
  </div>

  <h2>All 44 Strategies</h2>
  <div class="controls">
    <input type="text" id="search" placeholder="Search strategy...">
    <select id="filter">
      <option value="">All Indices</option>
      <option value="NIFTY">NIFTY</option>
      <option value="SENSEX">SENSEX</option>
      <option value="BANKNIFTY">BANKNIFTY</option>
    </select>
  </div>

  <table id="table">
    <thead>
      <tr>
        <th>Strategy</th>
        <th>Trades</th>
        <th>Win Rate</th>
        <th>Profit Factor</th>
        <th>Total P&L</th>
        <th>Max Drawdown</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
</div>

<script>
const DATA = {data_json};

function fmt(v) {{ return v.toLocaleString('en-IN', {{maximumFractionDigits: 2}}); }}
function fmtCur(v) {{ return (v >= 0 ? '+₹' : '₹') + fmt(Math.abs(v)); }}

// Render KPIs
function renderKPIs() {{
  let totalTrades = 0, totalWins = 0, totalPnL = 0, profit = 0, loss = 0;
  Object.values(DATA).forEach(s => {{
    totalTrades += s.total_trades;
    totalWins += Math.round(s.total_trades * s.win_rate / 100);
    totalPnL += s.total_pnl;
    if (s.total_pnl > 0) profit += s.total_pnl;
    else loss += Math.abs(s.total_pnl);
  }});

  const avgWR = (totalWins / totalTrades * 100).toFixed(1);
  const pf = loss > 0 ? (profit / loss).toFixed(2) : '999.99';

  const html = `
    <div class="kpi">
      <div class="kpi-label">Total Trades</div>
      <div class="kpi-value">${{fmt(totalTrades)}}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Avg Win Rate</div>
      <div class="kpi-value pos">${{avgWR}}%</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Total P&L</div>
      <div class="kpi-value ${{totalPnL >= 0 ? 'pos' : 'neg'}}">${{fmtCur(totalPnL)}}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Profit Factor</div>
      <div class="kpi-value pos">${{pf}}</div>
    </div>
  `;
  document.getElementById('kpis').innerHTML = html;
}}

// Get index stats
function getIndexStats() {{
  const stats = {{}};
  Object.entries(DATA).forEach(([name, s]) => {{
    const idx = name.split('_')[0];
    if (!stats[idx]) stats[idx] = {{trades: 0, wins: 0, pnl: 0}};
    stats[idx].trades += s.total_trades;
    stats[idx].wins += Math.round(s.total_trades * s.win_rate / 100);
    stats[idx].pnl += s.total_pnl;
  }});
  Object.keys(stats).forEach(idx => {{
    stats[idx].wr = (stats[idx].wins / stats[idx].trades * 100).toFixed(1);
  }});
  return stats;
}}

// Charts
const indexStats = getIndexStats();
const indices = Object.keys(indexStats).sort();

new Chart(document.getElementById('chart1'), {{
  type: 'bar',
  data: {{
    labels: indices,
    datasets: [{{ label: 'Win Rate %', data: indices.map(i => indexStats[i].wr), backgroundColor: '#3b82f6' }}]
  }},
  options: {{ indexAxis: 'y', responsive: true, plugins: {{ legend: {{ display: false }} }} }}
}});

new Chart(document.getElementById('chart2'), {{
  type: 'bar',
  data: {{
    labels: indices,
    datasets: [{{ label: 'P&L ₹', data: indices.map(i => indexStats[i].pnl), backgroundColor: indices.map(i => indexStats[i].pnl >= 0 ? '#22c55e' : '#ef4444') }}]
  }},
  options: {{ indexAxis: 'y', responsive: true, plugins: {{ legend: {{ display: false }} }} }}
}});

const top10 = Object.entries(DATA).sort((a,b) => b[1].total_pnl - a[1].total_pnl).slice(0, 10);
new Chart(document.getElementById('chart3'), {{
  type: 'bar',
  data: {{
    labels: top10.map(([n]) => n.substring(0, 22) + '...'),
    datasets: [{{ label: 'P&L ₹', data: top10.map(([,s]) => s.total_pnl), backgroundColor: '#10b981' }}]
  }},
  options: {{ indexAxis: 'y', responsive: true, plugins: {{ legend: {{ display: false }} }} }}
}});

// Table
function renderTable() {{
  const search = document.getElementById('search').value.toUpperCase();
  const filter = document.getElementById('filter').value;
  const rows = Object.entries(DATA).filter(([n,s]) =>
    (!search || n.includes(search)) && (!filter || n.startsWith(filter))
  ).sort((a,b) => b[1].total_pnl - a[1].total_pnl);

  const html = rows.map(([n, s]) => `<tr>
    <td><strong>${{n}}</strong><br><span class="badge badge-${{s.direction.toLowerCase()}}">${{s.direction}}</span></td>
    <td>${{s.total_trades}}</td>
    <td><span class="pos">${{s.win_rate.toFixed(1)}}%</span></td>
    <td>${{s.profit_factor.toFixed(2)}}</td>
    <td><span class="${{s.total_pnl >= 0 ? 'pos' : 'neg'}}">${{fmtCur(s.total_pnl)}}</span></td>
    <td>${{s.max_drawdown_pct.toFixed(2)}}%</td>
  </tr>`).join('');
  document.getElementById('tbody').innerHTML = html;
}}

renderKPIs();
renderTable();
document.getElementById('search').addEventListener('input', renderTable);
document.getElementById('filter').addEventListener('change', renderTable);
</script>

</body>
</html>
"""

Path("data/backtest_results/backtest_report.html").write_text(html, encoding='utf-8')
print("OK Report rebuilt")
print(f"OK {len(data)} strategies embedded")
