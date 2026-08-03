"""Loads .env and config/risk_params.json into a single validated Config object."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    fyers_client_id: str
    fyers_secret_key: str
    fyers_fy_id: str
    fyers_user_pin: str
    fyers_totp_secret: str
    fyers_redirect_uri: str
    telegram_bot_token: str
    telegram_chat_id: str
    force_market_open: bool
    risk_params: dict = field(default_factory=dict)

    @staticmethod
    def load(env_path: Path = None, risk_params_path: Path = None) -> "Config":
        load_dotenv(env_path or PROJECT_ROOT / ".env")

        risk_params_path = risk_params_path or PROJECT_ROOT / "config" / "risk_params.json"
        with open(risk_params_path, "r", encoding="utf-8") as f:
            risk_params = json.load(f)

        return Config(
            fyers_client_id=os.getenv("FYERS_CLIENT_ID", ""),
            fyers_secret_key=os.getenv("FYERS_SECRET_KEY", ""),
            fyers_fy_id=os.getenv("FYERS_FY_ID", ""),
            fyers_user_pin=os.getenv("FYERS_USER_PIN", ""),
            fyers_totp_secret=os.getenv("FYERS_TOTP_SECRET", ""),
            fyers_redirect_uri=os.getenv("FYERS_REDIRECT_URI", "https://127.0.0.1:8000/callback"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            force_market_open=os.getenv("FORCE_MARKET_OPEN", "false").strip().lower() == "true",
            risk_params=risk_params,
        )

    def validate(self, require_fyers: bool = True, require_telegram: bool = False) -> None:
        missing = []
        if require_fyers:
            for field_name in (
                "fyers_client_id",
                "fyers_secret_key",
                "fyers_fy_id",
                "fyers_user_pin",
                "fyers_totp_secret",
            ):
                if not getattr(self, field_name):
                    missing.append(field_name.upper())
        if require_telegram:
            for field_name in ("telegram_bot_token", "telegram_chat_id"):
                if not getattr(self, field_name):
                    missing.append(field_name.upper())
        if missing:
            raise ValueError(f"Missing required config values: {', '.join(missing)}")
