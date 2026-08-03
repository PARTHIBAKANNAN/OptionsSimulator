# Setup

## 1. Install

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### If pip fails to build pandas from source
That means Python is newer than the pinned pandas/numpy have wheels for. `requirements.txt` is
already pinned to versions with Python 3.13 wheels (`pandas==2.2.3`, `numpy==2.1.3`); if you're on
an even newer Python, bump both further.

### If import fails with `ModuleNotFoundError: No module named 'pkg_resources'`
`fyers-apiv3`'s WebSocket module imports `pkg_resources`, which recent `setuptools` no longer
ships. Already pinned in `requirements.txt` (`setuptools<81`) — if it still happens, re-run
`pip install -r requirements.txt`.

### If you're on a corporate network and get `SSLCertVerificationError`
TLS-inspecting proxies (Zscaler, Netskope, etc.) aren't in `requests`' bundled CA list. Already
handled — `src/fyers/api_client.py` calls `truststore.inject_into_ssl()` to use the OS certificate
store instead, which already trusts your corporate proxy's root CA.

## 2. Credentials (`.env`)

Copy `.env.example` to `.env` and fill in:

| Variable | Where to get it |
|---|---|
| `FYERS_CLIENT_ID` | `myapi.fyers.in` → your app → App ID + `-100` suffix (e.g. `ABCDE12345-100`) |
| `FYERS_SECRET_KEY` | Same app page |
| `FYERS_FY_ID` | Your Fyers login ID |
| `FYERS_USER_PIN` | Your 4-digit trading PIN |
| `FYERS_TOTP_SECRET` | The base32 secret from when you set up 2FA (long-press the entry in your authenticator app) |
| `FYERS_REDIRECT_URI` | Must exactly match the redirect URI registered on the app page |
| `TELEGRAM_BOT_TOKEN` | Message `@BotFather` on Telegram → `/newbot` |
| `TELEGRAM_CHAT_ID` | See below |

### Getting your Telegram chat ID
1. Message your bot anything (e.g. `/start`).
2. Open `https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates` in a browser.
3. Find `"chat":{"id": 123456789, ...}` in the response — that's your `TELEGRAM_CHAT_ID`.
4. If the response is empty, you haven't messaged the bot yet — do that first, then reload.

### One-time app authorization
A freshly created Fyers app needs its first login to go through the standard browser OAuth consent
screen before the automated TOTP flow will work reliably against it. If `fetch_historical_data.py`
or `main.py` fail on first run with an auth error, check the app's status on
`myapi.fyers.in/web/api-dashboard/user-apps` — it should show **Connected**.

## 3. Historical data

```bash
python fetch_historical_data.py 90
```

Logs into Fyers (TOTP), pulls 90 days of 1-minute NIFTY candles, saves to
`data/historical/nifty_90days.csv`. This performs a real (read-only) login against your live Fyers
account — no orders are placed.

If you'd rather not use the API for this, export manually from the Fyers web charting platform
(NIFTY, 1-minute, last 90 days, export CSV) with columns `Timestamp,Open,High,Low,Close,Volume`.

## 4. Run the backtest (CLI)

```bash
python main.py
# equivalent to: python -m src.backtester.backtest_engine
```

## 5. Run the web app (live paper trading + dashboard)

Live trading and its UI moved to `backend/` + `frontend/` — see `docs/ARCHITECTURE.md` for why.

### Backend
```bash
pip install -r backend/requirements.txt
```
Add to `.env` (see `.env.example` for the full list): `SESSION_SECRET`, `SUPABASE_URL`,
`SUPABASE_DB_URL`. Get these from a Supabase project (free tier) — Settings → API for the URL,
Settings → Database → Connection string (transaction pooler, port 6543) for `SUPABASE_DB_URL`.
Then run `backend/migrations/001_options_positions.sql` once in that project's SQL editor.

```bash
python backend/run.py
```
Runs on `http://127.0.0.1:8001`. `DATA_ENGINE_ENABLED=false` (the default) replays historical data
instead of connecting to live Fyers — useful for local dev without live credentials or market
hours, and it's also what runs if live WebSocket access is blocked (see the network note below).

### Frontend
```bash
cd frontend
npm install
cp .env.example .env   # fill in VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY (same Supabase project)
npm run dev
```
Runs on `http://localhost:5173`, proxying `/api` and `/ws` to the backend on port 8001.

## 6. Test

```bash
pytest tests/ backend/tests/ -v   # 54 tests
cd frontend && npm run build       # verifies the frontend actually compiles
```

## Operational note: don't run alongside other Fyers sessions

Fyers allows only one live WebSocket connection per app. If you also run a related project against
the *same* Fyers app (check `FYERS_CLIENT_ID`/`FYERS_FY_ID` in both `.env` files), don't run both
live at once — they'll fight over the one connection. Using a separate Fyers app per instance (as
this project does) avoids the conflict entirely.

## Deploying

See `deploy/README.md` for the full one-time VM setup + GitHub Actions CI/CD pipeline
(`.github/workflows/deploy.yml`).
