"""
FastAPI app: session+CORS middleware (session must stay inside CORS — added first so it's the
innermost layer), Supabase-JWT login bridge, WebSocket streaming, and the paper-trading/backtest
routers. Lifespan starts the DB pool, the live engine (or replay fallback), and the broadcaster.
"""
import asyncio

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
    supabase_auth.configure(config.supabase_url)
    if not config.supabase_url:
        logger.log_error("SUPABASE_URL not set — login will be rejected until it's configured")

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
    return {
        "status": "ok",
        "mode": "live" if engine.data_engine_enabled else "replay",
        "fyers_authenticated": bool(engine.fyers.access_token) if engine.data_engine_enabled else None,
        "is_running": engine.is_running,
        "db_available": request.app.state.db_available,
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
        user = supabase_auth.verify_token(token)
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
                    "nifty_price": cached.get("nifty_price", 24823.15),
                    "nifty_change": cached.get("nifty_change", 142.50),
                    "nifty_change_pct": cached.get("nifty_change_pct", 0.58),
                    "sensex_price": cached.get("sensex_price", 81388.40),
                    "sensex_change": cached.get("sensex_change", 450.20),
                    "sensex_change_pct": cached.get("sensex_change_pct", 0.56),
                    "market_open": current_state.get("market_open", False),
                    "strategies_count": 21,
                }
        except Exception:
            pass

    return {
        "nifty_price": nifty or 24823.15,
        "nifty_change": current_state.get("nifty_change") or 142.50,
        "nifty_change_pct": current_state.get("nifty_change_pct") or 0.58,
        "sensex_price": sensex or 81388.40,
        "sensex_change": current_state.get("sensex_change") or 450.20,
        "sensex_change_pct": current_state.get("sensex_change_pct") or 0.56,
        "market_open": current_state.get("market_open", False),
        "strategies_count": 21,
    }


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
