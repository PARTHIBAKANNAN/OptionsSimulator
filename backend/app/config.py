"""Extends src/config.py's Config with the web-layer settings the CLI doesn't need."""
import os
from dataclasses import dataclass

from src.config import Config


@dataclass
class WebConfig:
    base: Config
    cors_origins: list[str]
    stream_interval: float
    session_secret: str
    supabase_url: str
    supabase_db_url: str
    port: int
    data_engine_enabled: bool
    instance_name: str

    @staticmethod
    def load() -> "WebConfig":
        base = Config.load()  # already calls load_dotenv()
        cors_origins = [
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if o.strip()
        ]
        return WebConfig(
            base=base,
            cors_origins=cors_origins,
            stream_interval=float(os.getenv("STREAM_INTERVAL", "1.0")),
            session_secret=os.getenv("SESSION_SECRET", ""),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_db_url=os.getenv("SUPABASE_DB_URL", ""),
            port=int(os.getenv("PORT", "8001")),
            data_engine_enabled=os.getenv("DATA_ENGINE_ENABLED", "false").strip().lower() == "true",
            instance_name=os.getenv("INSTANCE_NAME", "local"),
        )

    def validate(self) -> None:
        missing = [name for name, val in (
            ("SESSION_SECRET", self.session_secret),
            ("SUPABASE_URL", self.supabase_url),
            ("SUPABASE_DB_URL", self.supabase_db_url),
        ) if not val]
        if missing:
            raise ValueError(f"Missing required web config values: {', '.join(missing)}")
