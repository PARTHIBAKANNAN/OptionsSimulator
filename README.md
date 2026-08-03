# NIFTY Options Paper Trader

Paper-trading only — no real orders are ever placed. Six intraday strategies (3 CE / 3 PE) run in
parallel against live NIFTY data from Fyers; qualifying signals are simulated through an internal
paper trader with stop-loss/take-profit/time-exit, approved via Telegram or the web dashboard.

A FastAPI + React web app (`backend/` + `frontend/`) provides live trading, the backtest report,
and trade history; the CLI (`main.py`) is now backtest-only. See
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for why.

## Quickstart

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # fill in Fyers + Telegram credentials
python fetch_historical_data.py 90   # pulls 90 days of NIFTY 1-min candles
python main.py                       # runs the backtest
pytest tests/ backend/tests/ -v      # 54 tests
```

Web app (live trading + dashboard) — needs a Supabase project too, see
**[docs/SETUP.md](docs/SETUP.md)**:

```bash
pip install -r backend/requirements.txt && python backend/run.py   # :8001
cd frontend && npm install && npm run dev                          # :5173
```

## Docs

- **[docs/SETUP.md](docs/SETUP.md)** — install, credentials, historical data, running the CLI and web app, troubleshooting
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — module map, data flow, design decisions and why
- **[docs/STRATEGIES.md](docs/STRATEGIES.md)** — the 6 strategies, entry conditions, risk parameters
- **[deploy/README.md](deploy/README.md)** — one-time VM setup + GitHub Actions CI/CD pipeline
- **[docs/planning-archive/](docs/planning-archive/)** — original pre-implementation planning docs (superseded, kept for history)

## Known open items

- `TELEGRAM_CHAT_ID` is not yet in `.env` — see [docs/SETUP.md](docs/SETUP.md#getting-your-telegram-chat-id).
- No Supabase project exists yet for the web app's auth/persistence — see
  [docs/SETUP.md](docs/SETUP.md#5-run-the-web-app-live-paper-trading--dashboard).
- Live WebSocket access to Fyers is currently blocked on the corporate network this was built on
  (Zscaler-suspect) — confirmed via a smoke test; the web app's replay mode works around this
  locally, but real live trading needs testing from elsewhere before trusting it.
- The exact Fyers option-symbol format (weekly expiry encoding) isn't hardcoded anywhere; confirm
  the current convention before relying on `get_option_chain`/live subscriptions for real strikes.
- Backtest results are a starting point for strategy selection, not validated live-trading performance.
- `.github/workflows/deploy.yml`/`deploy/deploy.sh` are written and validated locally (imports,
  `pytest`, frontend build) but not yet exercised against a real GitHub repo + the VM — that needs
  the repo + secrets set up first.
