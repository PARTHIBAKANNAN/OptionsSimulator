"""
Entry point. reload=False deliberately — Fyers allows only one WebSocket connection per app, and
uvicorn's --reload spawns a second worker process that would fight over that one connection.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `from src...`

import uvicorn

from app.config import WebConfig

if __name__ == "__main__":
    config = WebConfig.load()
    uvicorn.run("app.main:app", host="0.0.0.0", port=config.port, reload=False)
