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

        self.ws = None
        self.ws_spot = None
        self.ws_trades = None
        self._tick_callback = None
        self._subscribed_symbols: set[str] = set()
        self._spot_symbols: set[str] = {"NSE:NIFTY50-INDEX", "NSE:NIFTYBANK-INDEX", "BSE:SENSEX-INDEX"}
        self._trade_symbols: set[str] = set()

        cached = self._load_cached_token()
        if cached:
            self.access_token = cached
            self.fyers = self._build_model(cached)
        else:
            self.access_token = None
            self.fyers = None


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

    def _create_socket_instance(self, channel_name: str, symbols_set: set):
        def on_message(message):
            if self._tick_callback:
                self._tick_callback(message)

        def on_error(message):
            if self.logger:
                self.logger.log_error(f"websocket [{channel_name}] error: {message}")

        def on_close(message):
            if self.logger:
                self.logger.log_websocket_event(f"websocket_{channel_name}_closed", {"message": str(message)})

        def on_open():
            if self.logger:
                self.logger.log_websocket_event(f"websocket_{channel_name}_opened", {})
            if symbols_set:
                try:
                    time.sleep(0.5)
                    sock.subscribe(symbols=list(symbols_set), data_type="SymbolUpdate")
                    if self.logger:
                        self.logger.log_websocket_event(
                            f"websocket_{channel_name}_auto_resubscribed",
                            {"count": len(symbols_set)},
                        )
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(f"Auto-resubscribe failed on [{channel_name}] open: {e}")

        sock = data_ws.FyersDataSocket(
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
        return sock

    def start_websocket(self, on_tick_callback) -> None:
        if not self.access_token:
            raise FyersAuthError("Call authenticate_with_totp() before start_websocket()")
        self._tick_callback = on_tick_callback

        # 1. Primary / Discovery socket (Socket 3)
        self.ws = self._create_socket_instance("discovery", self._subscribed_symbols)
        self.ws.connect()

        # 2. Dedicated Spot Index socket (Socket 1: NIFTY, BANKNIFTY, SENSEX)
        try:
            self.ws_spot = self._create_socket_instance("spot", self._spot_symbols)
            self.ws_spot.connect()
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Failed to start dedicated spot websocket: {e}")

        # 3. Dedicated Active Trades socket (Socket 2: open positions across strategies)
        try:
            self.ws_trades = self._create_socket_instance("trades", self._trade_symbols)
            self.ws_trades.connect()
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Failed to start dedicated trades websocket: {e}")

    def subscribe_symbols(self, symbols: list) -> None:
        if not self.ws:
            raise FyersAuthError("Call start_websocket() before subscribe_symbols()")
        if symbols:
            self._subscribed_symbols.update(symbols)
            self.ws.subscribe(symbols=list(symbols), data_type="SymbolUpdate")

    def subscribe_trades_symbols(self, symbols: list) -> None:
        """Subscribes open trade contracts to the dedicated high-priority Socket 2."""
        if symbols:
            self._trade_symbols.update(symbols)
            if self.ws_trades:
                try:
                    self.ws_trades.subscribe(symbols=list(symbols), data_type="SymbolUpdate")
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(f"subscribe_trades_symbols failed: {e}")
            elif self.ws:
                self.subscribe_symbols(symbols)

    def unsubscribe_trades_symbols(self, symbols: list) -> None:
        """Unsubscribes closed trade contracts from the dedicated Socket 2."""
        if symbols:
            self._trade_symbols.difference_update(symbols)
            if self.ws_trades:
                try:
                    self.ws_trades.unsubscribe(symbols=list(symbols), data_type="SymbolUpdate")
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(f"unsubscribe_trades_symbols failed: {e}")

    def stop_websocket(self) -> None:
        """Closes the WebSocket connections but PRESERVES the subscription lists so that
        on_open's auto-resubscribe fires correctly when Fyers SDK reconnects or when
        the watchdog restarts the socket mid-session."""
        for sock in (self.ws, self.ws_spot, self.ws_trades):
            if sock:
                try:
                    sock.close_connection()
                except Exception:
                    pass

    def stop_websocket_final(self) -> None:
        """Full shutdown: clears subscriptions and closes all sockets. Use only at app exit."""
        self._subscribed_symbols.clear()
        self._trade_symbols.clear()
        self.stop_websocket()

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
