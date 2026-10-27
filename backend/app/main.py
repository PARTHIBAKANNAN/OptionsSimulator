"""
FastAPI app: session+CORS middleware (session must stay inside CORS — added first so it's the
innermost layer), Supabase-JWT login bridge, WebSocket streaming, and the paper-trading/backtest
routers. Lifespan starts the DB pool, the live engine (or replay fallback), and the broadcaster.
"""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.websockets import WebSocketState

from . import db, security, supabase_auth
from .backtest_router import router as backtest_router
from .broadcaster import Broadcaster
from .config import WebConfig
from .live_engine import WebLiveEngine
from .paper_router import router as paper_router
from .state import shared_state
from src.utils.logger import get_logger

config = WebConfig.load()
logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    supabase_auth.configure(config.supabase_url, jwt_secret=config.supabase_jwt_secret)
    if not supabase_auth.is_configured():
        logger.log_error("Neither SUPABASE_URL nor SUPABASE_JWT_SECRET set — login will be rejected")

    db_available = False
    if config.supabase_db_url:
        try:
            await db.init_pool(config.supabase_db_url)
            db_available = True
        except Exception as e:
            logger.log_error(f"DB pool init failed, running without persistence: {e}")
    else:
        logger.log_error("SUPABASE_DB_URL not set — running without persistence")
    app.state.db_available = db_available

    engine = WebLiveEngine(config.base, data_engine_enabled=config.data_engine_enabled)
    broadcaster = Broadcaster(shared_state.get, interval=config.stream_interval)
    app.state.live_engine = engine
    app.state.broadcaster = broadcaster

    engine_task = asyncio.create_task(engine.start())
    await broadcaster.start()

    try:
        yield
    finally:
        await engine.stop()
        engine_task.cancel()
        await broadcaster.stop()
        if db_available:
            await db.close_pool()


app = FastAPI(title="OptionsSimulator", lifespan=lifespan)

# session_cookie is explicitly namespaced: Starlette's SessionMiddleware defaults to a cookie
# literally named "session" on path "/" — TradeDashBoard's own backend uses the same default on
# the same domain (trading-dashboard-1.duckdns.org), so without this, whichever site you visit
# most recently overwrites the other's cookie (same name/domain/path, different secret_key), and
# the other site fails to decrypt it and treats you as logged out. See docs/ARCHITECTURE.md.
app.add_middleware(
    SessionMiddleware, secret_key=config.session_secret or "dev-only-insecure-secret",
    session_cookie="optionssimulator_session", same_site="lax",
)
app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins, allow_credentials=True,
                    allow_methods=["*"], allow_headers=["*"])

app.include_router(paper_router)
app.include_router(backtest_router)


@app.get("/api/health")
async def health(request: Request):
    engine: WebLiveEngine = request.app.state.live_engine
    broker = getattr(getattr(engine, "config", None), "broker", "aliceblue")
    is_auth = (
        bool(getattr(getattr(engine, "aliceblue", None), "is_authenticated", False))
        if broker == "aliceblue"
        else (bool(engine.fyers.access_token) if engine.data_engine_enabled else None)
    )
    return {
        "status": "ok",
        "mode": "live" if engine.data_engine_enabled else "replay",
        "broker": broker,
        "aliceblue_authenticated": is_auth,
        "broker_authenticated": is_auth,
        "is_running": engine.is_running,
        "db_available": request.app.state.db_available,
    }


@app.get("/api/health/master")
async def master_health(request: Request):
    """Comprehensive diagnostic endpoint checking all indices, data feeds, indicators,
    and strategy engines for live readiness."""
    from datetime import datetime
    from src.trader import IST
    from src.utils.options_pricing import next_weekly_expiry_date
    engine: WebLiveEngine = request.app.state.live_engine
    now = datetime.now(IST)

    indices_diag = {}
    for idx_name in ("NIFTY", "SENSEX", "BANKNIFTY"):
        dm = engine.data_managers.get(idx_name)
        if dm:
            state = dm.get_state()
            cached_ind = getattr(dm, "_cached_values", {})
            candles = getattr(dm, "candles", [])
            chain = dm.get_option_chain()
            next_exp = next_weekly_expiry_date(now, index=idx_name)
            indices_diag[idx_name] = {
                "spot_price": state.get("nifty_price"),
                "candles_count": len(candles),
                "latest_candle_time": candles[-1].timestamp.isoformat() if candles else None,
                "has_50_ema_1h": "ema_50_1h" in cached_ind or "ema_50_5m" in cached_ind,
                "cached_indicators_count": len(cached_ind),
                "option_chain_quotes_count": len(chain),
                "next_expiry_date": next_exp.isoformat(),
            }
        else:
            indices_diag[idx_name] = {"error": "DataManager not initialized"}

    positions_diag = []
    if hasattr(engine, "quote_store"):
        for o in engine.paper_trader.get_positions():
            snap = engine.quote_store.get_snapshot(getattr(o, "canonical_id", None)) if getattr(o, "canonical_id", None) else None
            if snap is None and getattr(o, "fyers_symbol", None):
                snap = engine.quote_store.get_snapshot_by_symbol(o.fyers_symbol)
            positions_diag.append({
                "symbol": o.symbol,
                "fyers_symbol": getattr(o, "fyers_symbol", None),
                "strategy": o.strategy,
                "entry_price": o.entry_price,
                "ws_ltp": snap.ltp if snap else None,
                "ws_source": snap.source if snap else None,
                "ws_age_ms": round(snap.age_ms(), 1) if snap else None,
            })

    strategy_counts = {idx: len(se.strategies) for idx, se in getattr(engine, "strategy_engines", {}).items()}
    total_strategies = sum(strategy_counts.values())

    readiness = getattr(engine, "readiness_stage", None)
    readiness_name = readiness.name if hasattr(readiness, "name") else str(readiness) if readiness else "NOT_INITIALIZED"

    market_data_diag = {
        "readiness_state": readiness_name,
        "instruments_registered": len(getattr(getattr(engine, "instrument_registry", None), "_by_canonical_id", {})),
        "quotes_in_store": len(getattr(getattr(engine, "quote_store", None), "_snapshots_by_canonical", {})),
        "active_quotes_2s": engine.quote_store.get_active_quote_count(2000.0) if hasattr(engine, "quote_store") else 0,
        "quote_validator_active": hasattr(engine, "quote_validator"),
        "atm_window_strikes": getattr(engine, "atm_window_strikes", None),
    }

    return {
        "status": "ok",
        "timestamp": now.isoformat(),
        "mode": "live" if engine.data_engine_enabled else "replay",
        "is_running": engine.is_running,
        "db_available": request.app.state.db_available,
        "market_data": market_data_diag,
        "broker": getattr(getattr(engine, "config", None), "broker", "aliceblue"),
        "aliceblue": {
            "authenticated": bool(getattr(getattr(engine, "aliceblue", None), "is_authenticated", False) if getattr(getattr(engine, "config", None), "broker", "aliceblue") == "aliceblue" else (engine.fyers.access_token if engine.data_engine_enabled else False)),
            "connected": getattr(engine, "_connected", False),
            "monitored_symbols_count": len(getattr(getattr(getattr(engine, "aliceblue", None), "ws", None), "_subscribed_keys", set()) if getattr(getattr(engine, "config", None), "broker", "aliceblue") == "aliceblue" else getattr(engine, "_monitored_symbols", set())),
            "monitored_symbols": sorted(list(getattr(getattr(getattr(engine, "aliceblue", None), "ws", None), "_subscribed_keys", set()) if getattr(getattr(engine, "config", None), "broker", "aliceblue") == "aliceblue" else getattr(engine, "_monitored_symbols", set()))),
        },
        "indices": indices_diag,
        "positions_diag": positions_diag,
        "strategies": {
            "total_active": total_strategies,
            "by_index": strategy_counts,
            "open_positions": len(engine.paper_trader.get_positions()),
        },
    }


@app.post("/api/public/fetch-contract-candles")
async def fetch_contract_candles(request: Request):
    """Fetches real 1-minute historical candles from Fyers for given symbols using the active authenticated session."""
    body = await request.json()
    symbols = body.get("symbols", [])
    days = int(body.get("days", 2))
    engine: WebLiveEngine = request.app.state.live_engine
    
    results = {}
    for sym in symbols:
        try:
            loop = asyncio.get_running_loop()
            df = await loop.run_in_executor(
                None, engine.fyers.get_historical_data, sym, "1", days
            )
            if df is not None and not df.empty:
                records = []
                for _, row in df.iterrows():
                    ts = row["Timestamp"]
                    records.append({
                        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": int(row["Volume"]) if "Volume" in row else 0,
                    })
                results[sym] = records
            else:
                results[sym] = []
        except Exception as e:
            results[sym] = {"error": str(e)}
            
    return {"status": "ok", "candles": results}


@app.get("/api/public/candles/{index}")
async def get_index_candles(index: str, timeframe: str = "5m", days: int = 5, request: Request = None):
    """Returns resampled OHLCV + CVD delta candles for NIFTY, BANKNIFTY, or SENSEX
    supporting timeframes: 1m, 3m, 5m, 15m, 1h, 1D. Seamlessly falls back to recent
    historical cache if exchange is closed or engine is pre-market."""
    idx_upper = index.upper()
    if idx_upper not in ("NIFTY", "BANKNIFTY", "SENSEX"):
        raise HTTPException(status_code=400, detail="Invalid index. Choose NIFTY, BANKNIFTY, or SENSEX.")

    from datetime import datetime, timedelta
    from pathlib import Path
    from src.trader import IST
    import pandas as pd
    import src.db.sqlite_candle_cache as sqlite_cache

    tf_map = {
        "1m": "1min",
        "3m": "3min",
        "5m": "5min",
        "15m": "15min",
        "1h": "1h",
        "1D": "1D",
    }
    rule = tf_map.get(timeframe, "5min")

    # 1. Check live memory + SQLite cache
    closed_candles = []
    try:
        engine = getattr(getattr(request, "app", None), "state", None)
        engine_obj = getattr(engine, "live_engine", None)
        dm = getattr(engine_obj, "data_managers", {}).get(idx_upper) if engine_obj else None

        sqlite_candles = sqlite_cache.load_recent_candles(idx_upper, days=max(days, 30))
        candle_dict = {c.timestamp: c for c in sqlite_candles}
        if dm and hasattr(dm, "candles"):
            for c in getattr(dm, "candles", []):
                candle_dict[c.timestamp] = c
        closed_candles = sorted(candle_dict.values(), key=lambda c: c.timestamp)
    except Exception:
        pass

    # 2. If live memory + SQLite has sufficient bars, resample and return
    if len(closed_candles) >= 10:
        try:
            df = pd.DataFrame([{
                "Timestamp": c.timestamp, "Open": c.open, "High": c.high, "Low": c.low,
                "Close": c.close, "Volume": c.volume, "Delta": c.delta,
            } for c in closed_candles])
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True, errors="coerce")
            df = df.dropna(subset=["Timestamp"]).sort_values("Timestamp").set_index("Timestamp")

            resampled = df.resample(rule).agg({
                "Open": "first", "High": "max", "Low": "min", "Close": "last",
                "Volume": "sum", "Delta": "sum",
            }).dropna()

            bars = []
            for ts, row in resampled.iterrows():
                bars.append({
                    "time": int(ts.timestamp()),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": float(row["Volume"]),
                    "delta": round(float(row["Delta"]), 1),
                })
            if bars:
                return {"status": "ok", "index": idx_upper, "timeframe": timeframe, "candles": bars}
        except Exception:
            pass

    # 3. Off-market or initial startup fallback: query live exchange via yfinance
    try:
        import yfinance as yf
        ticker_map = {"NIFTY": "^NSEI", "SENSEX": "^BSESN", "BANKNIFTY": "^NSEBANK"}
        ticker = ticker_map.get(idx_upper)
        if ticker:
            ydf = yf.download(ticker, period="5d", interval="1m", progress=False)
            if not ydf.empty:
                clean_df = pd.DataFrame({
                    "Open": ydf["Open"].to_numpy().flatten().astype(float),
                    "High": ydf["High"].to_numpy().flatten().astype(float),
                    "Low": ydf["Low"].to_numpy().flatten().astype(float),
                    "Close": ydf["Close"].to_numpy().flatten().astype(float),
                    "Volume": ydf["Volume"].to_numpy().flatten().astype(float),
                }, index=pd.to_datetime(ydf.index, utc=True))

                resampled = clean_df.resample(rule).agg({
                    "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
                }).dropna()

                bars = []
                for ts, row in resampled.iterrows():
                    bars.append({
                        "time": int(ts.timestamp()),
                        "open": round(float(row["Open"]), 2),
                        "high": round(float(row["High"]), 2),
                        "low": round(float(row["Low"]), 2),
                        "close": round(float(row["Close"]), 2),
                        "volume": float(row.get("Volume", 0)),
                        "delta": 0.0,
                    })
                if bars:
                    return {"status": "ok", "index": idx_upper, "timeframe": timeframe, "candles": bars}
    except Exception:
        pass

    return {"status": "ok", "index": idx_upper, "timeframe": timeframe, "candles": []}


@app.get("/api/public/telemetry")
async def get_telemetry(request: Request):
    """Detailed latency and WebSocket diagnostic metrics for real-time verification."""
    from datetime import datetime
    import time
    from src.trader import IST
    engine: WebLiveEngine = request.app.state.live_engine
    now = datetime.now(IST)

    broker = getattr(getattr(engine, "config", None), "broker", "aliceblue")
    ab = getattr(engine, "aliceblue", None)
    ws = getattr(ab, "ws", None) if ab else None

    quote_store = getattr(engine, "quote_store", None)
    qs_snapshots = getattr(quote_store, "_snapshots_by_canonical", {}) if quote_store else {}

    active_quotes_1s = quote_store.get_active_quote_count(1000.0) if quote_store else 0
    active_quotes_2s = quote_store.get_active_quote_count(2000.0) if quote_store else 0

    now_perf = time.time()
    ages_ms = []
    for snap in qs_snapshots.values():
        try:
            if hasattr(snap, "age_ms"):
                ages_ms.append(round(snap.age_ms(), 1))
            elif getattr(snap, "receive_epoch_timestamp", 0) > 0:
                ages_ms.append(round((time.time() - snap.receive_epoch_timestamp) * 1000.0, 1))
        except Exception:
            pass

    avg_age_ms = round(sum(ages_ms) / len(ages_ms), 1) if ages_ms else 0.0
    min_age_ms = min(ages_ms) if ages_ms else 0.0


    spot_info = {}
    for idx in ("NIFTY", "BANKNIFTY", "SENSEX"):
        dm = engine.data_managers.get(idx)
        spot_info[idx] = {
            "price": getattr(dm, "_live_ltp", None) or (dm.candles[-1].close if dm and dm.candles else None),
            "candles_count": len(dm.candles) if dm else 0,
            "latest_candle": dm.candles[-1].timestamp.isoformat() if dm and dm.candles else None,
        }

    return {
        "status": "ok",
        "timestamp": now.isoformat(),
        "broker": broker,
        "is_connected": getattr(engine, "_connected", False),
        "is_authenticated": bool(getattr(ab, "is_authenticated", False)) if broker == "aliceblue" else bool(engine.fyers.access_token),
        "readiness_stage": getattr(engine, "readiness_stage", "INIT"),
        "corridor": {
            "total_tokens_subscribed": len(getattr(ws, "_subscribed_keys", set())) if ws else len(getattr(engine, "_monitored_symbols", set())),
            "instruments_registered": len(getattr(getattr(engine, "instrument_registry", None), "_by_canonical_id", {})),
            "quotes_in_store": len(qs_snapshots),
        },
        "latency_telemetry": {
            "target_window": "50ms - 150ms",
            "active_quotes_within_1s": active_quotes_1s,
            "active_quotes_within_2s": active_quotes_2s,
            "avg_quote_age_ms": avg_age_ms,
            "min_quote_age_ms": min_age_ms,
            "ws_connected": bool(ws.is_connected() if callable(getattr(ws, "is_connected", None)) else getattr(ws, "is_connected", False)) if ws else False,
        },
        "spot": spot_info,
    }


@app.get("/api/snapshot")
async def snapshot(user: dict = Depends(security.require_login)):
    return shared_state.get()


@app.post("/api/auth/login")
async def login(request: Request):
    body = await request.json()
    token = body.get("access_token")
    if not token:
        raise HTTPException(status_code=400, detail="access_token required")
    try:
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, supabase_auth.verify_token, token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    security.login_user(request, user)
    return user


@app.post("/api/auth/logout")
async def logout(request: Request):
    security.logout_user(request)
    return {"status": "ok"}


@app.get("/api/auth/me")
async def me(request: Request):
    user = security.current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _activate_corridor_subscription(engine: WebLiveEngine):
    now_ist = datetime.now(IST)
    engine._last_login_date = now_ist.date()
    engine._connected = True
    engine.readiness_stage = "SUBSCRIPTION_READY"
    spot_prices = {
        k: (getattr(dm.get_current_candle(), "close", 0.0) or (22500.0 if k == "NIFTY" else (55200.0 if k == "BANKNIFTY" else 81000.0)))
        for k, dm in engine.data_managers.items()
    }
    if hasattr(engine, "aliceblue") and engine.aliceblue:
        engine.aliceblue.subscribe_strike_corridor(spot_prices)


@app.get("/api/auth/aliceblue/login-url")
async def aliceblue_login_url(request: Request):
    """Returns official Alice Blue OAuth login URL for 1-click browser SSO."""
    engine: WebLiveEngine = request.app.state.live_engine
    app_code = getattr(getattr(engine, "aliceblue", None), "app_code", "82a1c6alep")
    return {
        "status": "ok",
        "app_code": app_code,
        "login_url": f"https://ant.aliceblueonline.com/?appcode={app_code}"
    }


@app.get("/api/auth/aliceblue/callback")
async def aliceblue_callback(request: Request):
    """Handles OAuth redirect from Alice Blue (https://ant.aliceblueonline.com/?appcode=...)."""
    from fastapi.responses import RedirectResponse
    auth_code = (
        request.query_params.get("authCode")
        or request.query_params.get("auth_code")
        or request.query_params.get("code")
        or ""
    ).strip()

    if not auth_code:
        return RedirectResponse(url="/?aliceblue_error=Missing+authCode", status_code=302)

    engine: WebLiveEngine = request.app.state.live_engine
    if not engine or not getattr(engine, "aliceblue", None):
        return RedirectResponse(url="/?aliceblue_error=Broker+not+configured", status_code=302)

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, engine.aliceblue.exchange_auth_code, auth_code)
    if not success:
        return RedirectResponse(url="/?aliceblue_error=Auth+exchange+failed", status_code=302)

    _activate_corridor_subscription(engine)
    logger.info("Alice Blue OAuth callback successful! Subscribed strike corridor.")
    return RedirectResponse(url="/?aliceblue_success=1", status_code=302)


@app.post("/api/auth/aliceblue/exchange")
async def aliceblue_exchange(request: Request):
    """JSON API to exchange authCode captured on the client side (SPA callback)."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    auth_code = (
        body.get("authCode")
        or body.get("auth_code")
        or body.get("code")
        or request.query_params.get("authCode")
        or ""
    ).strip()

    if not auth_code:
        raise HTTPException(status_code=400, detail="Missing authCode parameter")

    engine: WebLiveEngine = request.app.state.live_engine
    if not engine or not getattr(engine, "aliceblue", None):
        raise HTTPException(status_code=400, detail="Alice Blue broker not configured on this instance")

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, engine.aliceblue.exchange_auth_code, auth_code)
    if not success:
        raise HTTPException(status_code=401, detail="Alice Blue auth code exchange failed with broker")

    _activate_corridor_subscription(engine)
    logger.info("Alice Blue authCode exchanged via API! Subscribed strike corridor.")
    return {
        "status": "ok",
        "message": "Alice Blue authenticated and streaming live",
        "readiness_stage": engine.readiness_stage,
    }


@app.post("/api/auth/aliceblue/login")
async def aliceblue_login(request: Request):
    """Direct in-app Alice Blue login fallback: validates credentials and starts live broker streaming."""
    engine: WebLiveEngine = request.app.state.live_engine
    if not engine or not getattr(engine, "aliceblue", None):
        raise HTTPException(status_code=400, detail="Alice Blue broker not configured on this instance")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    totp = (body.get("totp") or "").strip()
    password = (body.get("password") or "").strip()
    user_id = (body.get("user_id") or "").strip()

    if user_id:
        engine.aliceblue.user_id = user_id

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None, engine.aliceblue.authenticate, totp, password
    )
    if not success:
        raise HTTPException(status_code=401, detail="Alice Blue authentication failed. Check credentials or TOTP.")

    engine.initialize_contracts()
    engine.aliceblue.connect_websocket()
    _activate_corridor_subscription(engine)
    return {"status": "ok", "message": "Alice Blue logged in and streaming live"}


@app.get("/api/public/market-summary")
async def get_public_market_summary():
    """Returns unauthenticated high-level market overview (NIFTY & SENSEX LTPs, market status)."""
    import json
    from pathlib import Path
    current_state = shared_state.get()
    nifty = current_state.get("nifty_price")
    sensex = current_state.get("sensex_price")
    
    if not nifty or not sensex:
        try:
            market_file = Path("data/last_market_state.json")
            if market_file.exists():
                cached = json.loads(market_file.read_text(encoding="utf-8"))
                return {
                    "nifty_price": cached.get("nifty_price", 22363.35),
                    "nifty_change": cached.get("nifty_change", -157.10),
                    "nifty_change_pct": cached.get("nifty_change_pct", -0.70),
                    "sensex_price": cached.get("sensex_price", 71924.68),
                    "sensex_change": cached.get("sensex_change", -547.65),
                    "sensex_change_pct": cached.get("sensex_change_pct", -0.76),
                    "banknifty_price": cached.get("banknifty_price", 54918.00),
                    "banknifty_change": cached.get("banknifty_change", -338.65),
                    "banknifty_change_pct": cached.get("banknifty_change_pct", -0.61),
                    "market_open": current_state.get("market_open", False),
                    "strategies_count": 44,
                }
        except Exception:
            pass

    return {
        "nifty_price": nifty or 22363.35,
        "nifty_change": current_state.get("nifty_change") or -157.10,
        "nifty_change_pct": current_state.get("nifty_change_pct") or -0.70,
        "sensex_price": sensex or 71924.68,
        "sensex_change": current_state.get("sensex_change") or -547.65,
        "sensex_change_pct": current_state.get("sensex_change_pct") or -0.76,
        "banknifty_price": current_state.get("banknifty_price") or 54918.00,
        "banknifty_change": current_state.get("banknifty_change") or -338.65,
        "banknifty_change_pct": current_state.get("banknifty_change_pct") or -0.61,
        "market_open": current_state.get("market_open", False),
        "strategies_count": 44,
    }



@app.websocket("/ws/public-ticker")
async def ws_public_ticker(websocket: WebSocket):
    """Public lightweight WebSocket broadcasting real-time spot index ticks (500ms). Zero sensitive math/signals."""
    await websocket.accept()
    import json
    from pathlib import Path

    def get_public_data():
        current_state = shared_state.get()
        nifty = current_state.get("nifty_price")
        sensex = current_state.get("sensex_price")
        if not nifty or not sensex:
            try:
                market_file = Path("data/last_market_state.json")
                if market_file.exists():
                    cached = json.loads(market_file.read_text(encoding="utf-8"))
                    return {
                        "nifty_price": cached.get("nifty_price", 22363.35),
                        "nifty_change": cached.get("nifty_change", -157.10),
                        "nifty_change_pct": cached.get("nifty_change_pct", -0.70),
                        "sensex_price": cached.get("sensex_price", 71924.68),
                        "sensex_change": cached.get("sensex_change", -547.65),
                        "sensex_change_pct": cached.get("sensex_change_pct", -0.76),
                        "banknifty_price": cached.get("banknifty_price", 54918.00),
                        "banknifty_change": cached.get("banknifty_change", -338.65),
                        "banknifty_change_pct": cached.get("banknifty_change_pct", -0.61),
                        "market_open": current_state.get("market_open", False),
                    }
            except Exception:
                pass
        return {
            "nifty_price": nifty or 22363.35,
            "nifty_change": current_state.get("nifty_change") or -157.10,
            "nifty_change_pct": current_state.get("nifty_change_pct") or -0.70,
            "sensex_price": sensex or 71924.68,
            "sensex_change": current_state.get("sensex_change") or -547.65,
            "sensex_change_pct": current_state.get("sensex_change_pct") or -0.76,
            "banknifty_price": current_state.get("banknifty_price") or 54918.00,
            "banknifty_change": current_state.get("banknifty_change") or -338.65,
            "banknifty_change_pct": current_state.get("banknifty_change_pct") or -0.61,
            "market_open": current_state.get("market_open", False),
        }

    try:
        last_sent = None
        while websocket.application_state == WebSocketState.CONNECTED:
            data = get_public_data()
            if data != last_sent:
                await websocket.send_text(json.dumps(data))
                last_sent = data
            await asyncio.sleep(0.5)
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        pass
    except Exception as e:
        logger.log_error(f"ws_public_ticker error: {e}")


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    if not security.is_authenticated_ws(websocket):
        await websocket.close(code=4401)
        return

    broadcaster: Broadcaster = websocket.app.state.broadcaster
    queue = broadcaster.subscribe()
    await websocket.send_text(broadcaster.snapshot_frame())

    def is_connected() -> bool:
        return websocket.application_state == WebSocketState.CONNECTED

    async def reader():
        try:
            while True:
                msg = await websocket.receive_json()
                if msg.get("type") == "resync" and is_connected():
                    await websocket.send_text(broadcaster.snapshot_frame())
        except (WebSocketDisconnect, RuntimeError):
            # RuntimeError: the ASGI connection was already torn down (client disconnected)
            # between us checking is_connected() and sending — same outcome, just stop.
            pass

    reader_task = asyncio.create_task(reader())
    try:
        while True:
            frame = await queue.get()
            if not is_connected():
                break
            await websocket.send_text(frame)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        reader_task.cancel()
        broadcaster.unsubscribe(queue)
