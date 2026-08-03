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

app.add_middleware(SessionMiddleware, secret_key=config.session_secret or "dev-only-insecure-secret", same_site="lax")
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


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    if not security.is_authenticated_ws(websocket):
        await websocket.close(code=4401)
        return

    broadcaster: Broadcaster = websocket.app.state.broadcaster
    queue = broadcaster.subscribe()
    await websocket.send_text(broadcaster.snapshot_frame())

    async def reader():
        try:
            while True:
                msg = await websocket.receive_json()
                if msg.get("type") == "resync":
                    await websocket.send_text(broadcaster.snapshot_frame())
        except WebSocketDisconnect:
            pass

    reader_task = asyncio.create_task(reader())
    try:
        while True:
            frame = await queue.get()
            await websocket.send_text(frame)
    except WebSocketDisconnect:
        pass
    finally:
        reader_task.cancel()
        broadcaster.unsubscribe(queue)
