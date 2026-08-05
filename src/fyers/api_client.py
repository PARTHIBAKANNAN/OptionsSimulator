"""
Fyers API v3 client: silent TOTP-based login (no manual browser step), WebSocket
tick streaming, and REST calls for option chain / historical data.

Order placement is intentionally NOT implemented here — this project is paper-trading
only (see FYERS_FEASIBILITY_REPORT.md: autonomous live orders carry SEBI compliance
risk). All simulated execution happens in src/simulator/paper_trader.py.
"""
import base64
import json
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import truststore
truststore.inject_into_ssl()  # trust the OS cert store (corporate TLS-inspecting proxies aren't in certifi)

import pyotp
import requests
import pandas as pd
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TOKEN_CACHE_PATH = PROJECT_ROOT / "fyers_token_cache.json"
SDK_LOG_DIR = PROJECT_ROOT / "logs"
SDK_LOG_DIR.mkdir(exist_ok=True)

IST = ZoneInfo("Asia/Kolkata")

BASE_URL = "https://api-t2.fyers.in"
URL_SEND_LOGIN_OTP = f"{BASE_URL}/vagator/v2/send_login_otp_v2"
URL_VERIFY_OTP = f"{BASE_URL}/vagator/v2/verify_otp"
URL_VERIFY_PIN = f"{BASE_URL}/vagator/v2/verify_pin_v2"
URL_TOKEN = "https://api-t1.fyers.in/api/v3/token"

RESOLUTION_SECONDS = {"1": 60, "5": 300, "15": 900, "60": 3600, "D": 86400}
MAX_CANDLES_PER_REQUEST_DAYS = 100  # Fyers caps ~100 days per history() call for intraday resolutions


class FyersAuthError(Exception):
    pass


class FyersAPIClient:
    def __init__(self, client_id: str, secret_key: str, fy_id: str, user_pin: str,
                 totp_secret: str, redirect_uri: str, logger=None):
        self.client_id = client_id
        self.secret_key = secret_key
        self.fy_id = fy_id
        self.user_pin = user_pin
        self.totp_secret = totp_secret
        self.redirect_uri = redirect_uri
        self.logger = logger

        self.access_token = None
        self.fyers = None
        self.ws = None
        self._tick_callback = None

    # ---- Authentication ----------------------------------------------------

    def authenticate_with_totp(self) -> str:
        """Full silent login: OTP -> TOTP verify -> PIN verify -> auth_code -> access_token."""
        cached = self._load_cached_token()
        if cached:
            self.access_token = cached
            self.fyers = self._build_model(cached)
            return cached

        fy_id_b64 = base64.b64encode(self.fy_id.encode()).decode()
        otp_res = requests.post(URL_SEND_LOGIN_OTP, json={"fy_id": fy_id_b64, "app_id": "2"}, timeout=10).json()
        if otp_res.get("s") != "ok":
            raise FyersAuthError(f"send_login_otp failed: {otp_res}")
        request_key = otp_res["request_key"]

        verify_res = None
        for _ in range(3):
            totp_code = pyotp.TOTP(self.totp_secret).now()
            verify_res = requests.post(
                URL_VERIFY_OTP, json={"request_key": request_key, "otp": totp_code}, timeout=10
            ).json()
            if verify_res.get("s") == "ok":
                break
            time.sleep(1)
        if not verify_res or verify_res.get("s") != "ok":
            raise FyersAuthError(f"verify_otp failed: {verify_res}")

        pin_b64 = base64.b64encode(self.user_pin.encode()).decode()
        pin_res = requests.post(
            URL_VERIFY_PIN,
            json={
                "request_key": verify_res["request_key"],
                "identity_type": "pin",
                "identifier": pin_b64,
            },
            timeout=10,
        ).json()
        if pin_res.get("s") != "ok":
            raise FyersAuthError(f"verify_pin failed: {pin_res}")

        auth_bearer = pin_res["data"]["access_token"]
        app_id, app_type = self._split_client_id()

        token_payload = {
            "fyers_id": self.fy_id,
            "app_id": app_id,
            "redirect_uri": self.redirect_uri,
            "appType": app_type,
            "code_challenge": "",
            "state": "trader_auto_login",
            "scope": "",
            "nonce": "",
            "response_type": "code",
            "create_cookie": True,
        }
        token_res = requests.post(
            URL_TOKEN, json=token_payload, headers={"authorization": f"Bearer {auth_bearer}"}, timeout=10
        ).json()
        redirect_url = token_res.get("Url")
        if not redirect_url:
            raise FyersAuthError(f"token exchange failed: {token_res}")

        auth_code = parse_qs(urlparse(redirect_url).query).get("auth_code", [None])[0]
        if not auth_code:
            raise FyersAuthError(f"no auth_code in redirect: {redirect_url}")

        session = fyersModel.SessionModel(
            client_id=self.client_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type="code",
            grant_type="authorization_code",
        )
        session.set_token(auth_code)
        auth_response = session.generate_token()
        access_token = auth_response.get("access_token")
        if not access_token:
            raise FyersAuthError(f"generate_token failed: {auth_response}")

        self.access_token = access_token
        self.fyers = self._build_model(access_token)
        self._save_token_cache(access_token)
        if self.logger:
            self.logger.log_websocket_event("fyers_auth_success", {"fy_id": self.fy_id})
        return access_token

    def refresh_access_token(self) -> bool:
        """Force a fresh login, bypassing any cached token (e.g. for the 08:30 daily refresh job)."""
        self._clear_token_cache()
        try:
            self.authenticate_with_totp()
            return True
        except FyersAuthError as e:
            if self.logger:
                self.logger.log_error(f"Token refresh failed: {e}")
            return False

    def _split_client_id(self):
        if "-" in self.client_id:
            app_id, app_type = self.client_id.rsplit("-", 1)
            return app_id, app_type
        return self.client_id, "100"

    def _build_model(self, access_token: str) -> fyersModel.FyersModel:
        return fyersModel.FyersModel(client_id=self.client_id, token=access_token, is_async=False,
                                      log_path=str(SDK_LOG_DIR))

    def _load_cached_token(self):
        if not TOKEN_CACHE_PATH.exists():
            return None
        try:
            cache = json.loads(TOKEN_CACHE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if cache.get("date") != time.strftime("%Y-%m-%d") or cache.get("fy_id") != self.fy_id:
            return None
        return cache.get("access_token")

    def _save_token_cache(self, access_token: str) -> None:
        TOKEN_CACHE_PATH.write_text(json.dumps({
            "access_token": access_token,
            "date": time.strftime("%Y-%m-%d"),
            "fy_id": self.fy_id,
        }))

    def _clear_token_cache(self) -> None:
        if TOKEN_CACHE_PATH.exists():
            TOKEN_CACHE_PATH.unlink()

    # ---- WebSocket -----------------------------------------------------------

    def start_websocket(self, on_tick_callback) -> None:
        if not self.access_token:
            raise FyersAuthError("Call authenticate_with_totp() before start_websocket()")
        self._tick_callback = on_tick_callback

        def on_message(message):
            self._tick_callback(message)

        def on_error(message):
            if self.logger:
                self.logger.log_error(f"websocket error: {message}")

        def on_close(message):
            if self.logger:
                self.logger.log_websocket_event("websocket_closed", {"message": str(message)})

        def on_open():
            if self.logger:
                self.logger.log_websocket_event("websocket_opened", {})

        self.ws = data_ws.FyersDataSocket(
            access_token=f"{self.client_id}:{self.access_token}",
            log_path=str(SDK_LOG_DIR),
            litemode=False,
            write_to_file=False,
            reconnect=True,
            on_connect=on_open,
            on_close=on_close,
            on_error=on_error,
            on_message=on_message,
        )
        self.ws.connect()

    def subscribe_symbols(self, symbols: list) -> None:
        if not self.ws:
            raise FyersAuthError("Call start_websocket() before subscribe_symbols()")
        self.ws.subscribe(symbols=symbols, data_type="SymbolUpdate")

    def stop_websocket(self) -> None:
        if self.ws:
            self.ws.close_connection()

    # ---- REST ------------------------------------------------------------

    def get_option_chain(self, symbol: str, strike_count: int = 10) -> dict:
        response = self.fyers.optionchain(data={"symbol": symbol, "strikecount": str(strike_count), "timestamp": ""})
        if response.get("s") != "ok":
            raise RuntimeError(f"get_option_chain failed: {response}")
        return response.get("data", {})

    def get_historical_data(self, symbol: str, resolution: str, days: int) -> pd.DataFrame:
        """Fetch up to `days` of historical candles, paging in chunks Fyers accepts per call."""
        all_rows = []
        end = int(time.time())
        remaining_days = days

        while remaining_days > 0:
            chunk_days = min(remaining_days, MAX_CANDLES_PER_REQUEST_DAYS)
            start = end - chunk_days * 86400
            response = self.fyers.history(data={
                "symbol": symbol,
                "resolution": resolution,
                "date_format": "0",
                "range_from": str(start),
                "range_to": str(end),
                "cont_flag": "1",
            })
            if response.get("s") != "ok":
                raise RuntimeError(f"get_historical_data failed: {response}")
            all_rows.extend(response.get("candles", []))
            end = start
            remaining_days -= chunk_days

        df = pd.DataFrame(all_rows, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
        # tz_convert(IST) (a zoneinfo.ZoneInfo object), not the string "Asia/Kolkata" — pandas
        # resolves a string zone name via pytz, while src/trader.py's on_tick() stamps live
        # candles with zoneinfo.ZoneInfo. Mixing a pytz-tz column with zoneinfo-tz values in the
        # same DataFrame (once _seed_historical_candles' rows and on_tick's live rows both land in
        # DataManager.candles) makes pandas fall back to a plain object-dtype Timestamp column
        # instead of datetime64[ns, tz] — which then makes .resample() raise
        # "Only valid with DatetimeIndex..." on every single tick, breaking indicator calculation
        # (and therefore every strategy) for the rest of the session. Consistent zoneinfo on both
        # sides avoids the mixed-dtype column entirely.
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="s", utc=True).dt.tz_convert(IST)
        df = df.sort_values("Timestamp").drop_duplicates(subset="Timestamp").reset_index(drop=True)
        return df
