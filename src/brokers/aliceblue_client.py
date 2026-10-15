"""
Unified Alice Blue Broker Client for OptionsSimulator
======================================================
Manages:
1. Daily 24-hr authentication (TOTP or cached user session).
2. Contract master downloads (NFO.csv / BFO.csv) and token resolution.
3. High-throughput NorenWS WebSocket streaming for Spot Indices and Option Corridor.
4. Seamless routing of live ticks directly to DataManager and QuoteStore.
"""
from datetime import date, datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import threading
import time
from typing import Callable, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo
import pyotp
import requests

from src.brokers.aliceblue_ws import AliceBlueWS
from src.market_data.contract_master import ContractMaster, ContractMeta, INDEX_SPOT_TOKENS
from src.market_data.instrument_registry import Instrument, InstrumentRegistry
from src.market_data.quote_store import QuoteStore

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


class AliceBlueClient:
    def __init__(
        self,
        user_id: str,
        password: str = "",
        totp_key: str = "",
        api_key: str = "",
        app_code: str = "82a1c6alep",
        session_token: str = "",
        token_cache_path: Optional[Path] = None,
        quote_store: Optional[QuoteStore] = None,
        instrument_registry: Optional[InstrumentRegistry] = None,
        data_managers: Optional[Dict[str, any]] = None,
        on_tick_hook: Optional[Callable[[], None]] = None,
    ):
        self.user_id = str(user_id).strip()
        self.password = str(password).strip()
        self.totp_key = str(totp_key).strip()
        self.api_key = str(api_key).strip()
        self.app_code = str(app_code or "82a1c6alep").strip()
        self._user_session = str(session_token).strip()

        self.token_cache_path = token_cache_path or (
            Path(__file__).resolve().parent.parent.parent / "data" / "aliceblue_token.json"
        )
        self.quote_store = quote_store
        self.instrument_registry = instrument_registry
        self.data_managers = data_managers or {}
        self.on_tick_hook = on_tick_hook

        # Components
        self.contract_master = ContractMaster()
        self.ws: Optional[AliceBlueWS] = None
        self._connected = False
        self._lock = threading.RLock()

        # Reverse lookup: token -> Instrument
        self._token_to_inst: Dict[int, Instrument] = {}
        # Reverse lookup: spot token -> underlying (e.g. 26000 -> NIFTY)
        self._spot_token_to_und: Dict[int, str] = {
            26000: "NIFTY",
            26009: "BANKNIFTY",
            1: "SENSEX",
        }

        # Attempt to restore cached session from disk on startup
        self._restore_session()

    @property
    def is_authenticated(self) -> bool:
        return bool(self._user_session and self._is_token_valid(self._user_session))

    @property
    def is_connected(self) -> bool:
        return bool(self.ws and self.ws.is_connected())

    def initialize(self, totp: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Loads cached session or logs in, loads contract master, and sets up WebSocket."""
        # 1. Authenticate / Restore Session
        if not self._restore_session():
            logger.info("No valid cached session found. Attempting login...")
            if not self.authenticate(totp=totp, password=password):
                logger.error("Alice Blue authentication failed.")
                return False

        # 2. Load Contract Master
        try:
            self.contract_master.load_contracts()
            self._sync_instruments_to_registry()
        except Exception as e:
            logger.error("Error loading ContractMaster: %s", e)
            return False

        # 3. Create WebSocket client
        self.ws = AliceBlueWS(
            user_id=self.user_id,
            user_session=self._user_session,
            on_tick_callback=self._on_ws_tick,
            on_connect_callback=self._on_ws_connected,
        )
        return True

    def connect_websocket(self) -> None:
        """Connects the WebSocket and begins streaming."""
        if not self.ws or not self._user_session:
            if not self.initialize():
                return
        if self.ws:
            self.ws.user_session = self._user_session
            self.ws.connect()
            self._connected = True

    def disconnect(self) -> None:
        if self.ws:
            self.ws.disconnect()
            self._connected = False

    def _is_token_valid(self, token_str: str) -> bool:
        try:
            parts = token_str.split(".")
            if len(parts) < 2:
                return False
            import base64
            payload_bytes = base64.b64decode(parts[1] + "==")
            payload = json.loads(payload_bytes.decode("utf-8"))
            exp = payload.get("exp", 0)
            if exp <= (time.time() + 300):
                return False
            # Check issued-at date in IST: broker sessions do not survive across calendar days
            iat = payload.get("iat", 0)
            if iat:
                iat_date = datetime.fromtimestamp(iat, tz=IST).date()
                today_date = datetime.now(IST).date()
                if iat_date < today_date:
                    logger.info("Alice Blue session was issued on %s (< today %s) - expired for morning login.", iat_date, today_date)
                    return False
            return True
        except Exception:
            return False

    def _restore_session(self) -> bool:
        today_date = datetime.now(IST).date()
        if self._user_session and self._is_token_valid(self._user_session):
            return True
        if self.token_cache_path.exists():
            try:
                data = json.loads(self.token_cache_path.read_text(encoding="utf-8"))
                cached_date = data.get("date")
                if cached_date and cached_date != today_date.isoformat():
                    logger.info("Cached Alice Blue session is from %s (< today %s) - requiring fresh daily login.", cached_date, today_date)
                    return False
                token = data.get("user_session") or data.get("userSession") or ""
                if self._is_token_valid(token):
                    self._user_session = token
                    logger.info("Restored valid Alice Blue session for today (%s)", today_date)
                    return True
            except Exception as e:
                logger.warning("Failed to restore session from cache: %s", e)
        return False

    def _evp_bytes_to_key(self, password: bytes, salt: bytes, key_len: int = 32, iv_len: int = 16):
        d = b""
        d_i = b""
        while len(d) < key_len + iv_len:
            d_i = hashlib.md5(d_i + password + salt).digest()
            d += d_i
        return d[:key_len], d[key_len: key_len + iv_len]

    def _encrypt_password_cryptojs(self, password: str, enc_key: str) -> str:
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
        except ImportError:
            raise RuntimeError("pycryptodome required: pip install pycryptodome")
        import base64, os
        salt = os.urandom(8)
        key, iv = self._evp_bytes_to_key(enc_key.encode("utf-8"), salt, 32, 16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        ct = cipher.encrypt(pad(password.encode("utf-8"), AES.block_size))
        return base64.b64encode(b"Salted__" + salt + ct).decode("utf-8")

    def generate_totp(self, totp_key: Optional[str] = None) -> str:
        key = (totp_key or self.totp_key).strip()
        if not key:
            raise ValueError("No TOTP key configured")
        return pyotp.TOTP(key).now()

    def authenticate(self, totp: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Performs 4-step direct login flow to acquire a 24-hr session token.
        Can be called with an explicit TOTP or will generate TOTP using self.totp_key.
        """
        if self._user_session and self._is_token_valid(self._user_session):
            self._save_session(self._user_session)
            return True

        user_id = self.user_id
        pwd = (password or self.password).strip()
        if not user_id or not pwd:
            logger.error("Alice Blue authentication failed: user_id or password missing.")
            return False

        otp = (totp or "").strip()
        if not otp:
            if self.totp_key:
                try:
                    otp = self.generate_totp()
                except Exception as e:
                    logger.error("Error generating TOTP: %s", e)
                    return False
            else:
                logger.error("Alice Blue authentication requires TOTP code or ALICEBLUE_TOTP_KEY.")
                return False

        BASE = "https://ant.aliceblueonline.com/omk"
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Origin": "https://ant.aliceblueonline.com",
            "Referer": "https://ant.aliceblueonline.com/",
        })

        try:
            # Step 1: verify/user
            r1 = session.post(f"{BASE}/auth/access/verify/user", json={"userId": user_id}, timeout=15)
            if r1.status_code != 200 or r1.json().get("status", "").lower() not in ("ok", "success", "true"):
                logger.error("verify/user failed: %s %s", r1.status_code, r1.text[:200])
                return False

            # Step 2: enckey
            r2 = session.post(f"{BASE}/auth/access/client/enckey", json={"userId": user_id}, timeout=15)
            if r2.status_code != 200:
                logger.error("enckey failed: %s %s", r2.status_code, r2.text[:200])
                return False
            d2 = r2.json()
            enc_key = None
            if isinstance(d2.get("result"), list) and len(d2["result"]) > 0:
                enc_key = d2["result"][0].get("encKey")
            if not enc_key:
                enc_key = d2.get("encKey") or d2.get("data", {}).get("encKey")
            if not enc_key:
                logger.error("encKey missing in response: %s", d2)
                return False

            # Step 3: pwd/validate
            encrypted_pwd = self._encrypt_password_cryptojs(pwd, enc_key)
            payload3 = {
                "userId": user_id,
                "userData": encrypted_pwd,
                "source": "WEB",
            }
            r3 = session.post(f"{BASE}/auth/access/v2/pwd/validate", json=payload3, timeout=15)
            if r3.status_code != 200:
                logger.error("pwd/validate failed: %s %s", r3.status_code, r3.text[:200])
                return False
            d3 = r3.json()
            step3_token = None
            if isinstance(d3.get("result"), list) and len(d3["result"]) > 0:
                step3_token = d3["result"][0].get("token")
            if not step3_token:
                step3_token = d3.get("token")
            if not step3_token:
                logger.error("pwd/validate missing token: %s", d3)
                return False

            # Step 4: topt/verify
            payload4 = {
                "userId": user_id,
                "totp": otp,
                "source": "WEB",
                "deviceId": "web_browser",
                "deviceNumber": "web_browser",
            }
            headers4 = {
                "Authorization": f"Bearer {user_id} WEB {step3_token}",
            }
            r4 = session.post(f"{BASE}/auth/access/topt/verify", json=payload4, headers=headers4, timeout=15)
            if r4.status_code != 200:
                logger.error("topt/verify failed: %s %s", r4.status_code, r4.text[:200])
                return False
            d4 = r4.json()
            access_token = None
            if isinstance(d4.get("result"), list) and len(d4["result"]) > 0:
                access_token = d4["result"][0].get("accessToken") or d4["result"][0].get("userSession")
            if not access_token:
                access_token = d4.get("accessToken") or d4.get("userSession")

            if not access_token:
                logger.error("topt/verify missing accessToken: %s", d4)
                return False

            self._user_session = access_token
            if self.ws:
                self.ws.user_session = access_token
            self._save_session(access_token)
            logger.info("Alice Blue direct login successful - session saved.")
            return True

        except Exception as e:
            logger.error("Exception during Alice Blue authenticate: %s", e)
            return False

    def get_login_url(self) -> str:
        """Returns official Alice Blue OAuth login URL."""
        return f"https://ant.aliceblueonline.com/?appcode={self.app_code}"

    def exchange_auth_code(self, auth_code: str) -> bool:
        """
        Exchanges official Alice Blue OAuth authCode for a userSession token
        using the vendor/getUserDetails API endpoint (Quantman SSO flow).
        """
        auth_code = str(auth_code or "").strip()
        if not auth_code:
            logger.error("exchange_auth_code called with empty auth_code")
            return False

        user_id = self.user_id or "2628887"
        app_secret = (self.api_key or "8G93PYak2ciy9jBAW9vjV6v7bLUJPvf8kVmFXySPcYqjkclvtKuYc5WIZi7gEQUyDkqfiNsX2lmc7XOpQ1WriuYA3m6D3cKxfZYE").strip()

        # Checksum = SHA256(userId + authCode + apiSecret)
        raw_str = f"{user_id}{auth_code}{app_secret}"
        checksum = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
        logger.info("Exchanging Alice Blue authCode for session (checksum=%s...)", checksum[:16])

        url = "https://a3.aliceblueonline.com/open-api/od/v1/vendor/getUserDetails"
        payload = {"checkSum": checksum}
        headers = {"Content-Type": "application/json"}

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code != 200:
                logger.error("getUserDetails failed with HTTP %d: %s", resp.status_code, resp.text[:300])
                return False

            data = resp.json()
            user_session = data.get("userSession") or data.get("user_session") or data.get("sessionID")
            if not user_session and isinstance(data.get("result"), list) and len(data["result"]) > 0:
                user_session = data["result"][0].get("userSession")
            if not user_session and isinstance(data.get("data"), dict):
                user_session = data["data"].get("userSession")

            if not user_session:
                logger.error("No userSession found in getUserDetails response: %s", data)
                return False

            self._user_session = user_session
            self._save_session(user_session)
            logger.info("Successfully exchanged authCode for Alice Blue session token!")

            # 2. Load Contract Master and index active contracts
            try:
                self.contract_master.load_contracts()
                self._sync_instruments_to_registry()
            except Exception as e:
                logger.error("Error loading ContractMaster: %s", e)

            # 3. Create or update WebSocket client
            if not self.ws:
                self.ws = AliceBlueWS(
                    user_id=self.user_id,
                    user_session=self._user_session,
                    on_tick_callback=self._on_ws_tick,
                    on_connect_callback=self._on_ws_connected,
                )
            else:
                self.ws.user_session = self._user_session

            # 4. Connect WebSocket
            self.connect_websocket()
            return True

        except Exception as e:
            logger.error("Exception in exchange_auth_code: %s", e)
            return False

    def _save_session(self, token: str) -> None:
        try:
            now_ist = datetime.now(IST)
            self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_cache_path.write_text(
                json.dumps({
                    "user_session": token,
                    "userSession": token,
                    "date": now_ist.date().isoformat(),
                    "updated_at": now_ist.isoformat(),
                }, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning("Could not cache session token: %s", e)

    def _sync_instruments_to_registry(self) -> None:
        """Syncs all active contract options into InstrumentRegistry and internal reverse map."""
        if not self.instrument_registry:
            return

        with self.instrument_registry._lock:
            for token, meta in self.contract_master._by_token.items():
                inst = Instrument(
                    underlying=meta.underlying,
                    expiry=meta.expiry,
                    strike=meta.strike,
                    option_type=meta.option_type,
                    exchange=meta.exchange,
                    fyers_symbol=meta.trading_symbol,  # Alias field for compatibility
                    lot_size=meta.lot_size,
                    tick_size=meta.tick_size,
                )
                self.instrument_registry._by_canonical_id[inst.canonical_id] = inst
                self.instrument_registry._clean_alias_to_canonical[inst.clean_alias] = inst.canonical_id
                self._token_to_inst[token] = inst

        logger.info("Synced %d instruments to InstrumentRegistry.", len(self._token_to_inst))

    def subscribe_strike_corridor(self, spot_prices: Dict[str, float]) -> None:
        """Subscribes ATM ± 15 strikes for active indices + spot tokens."""
        if not self.ws:
            return
        corridor = self.contract_master.get_corridor_tokens(spot_prices, strikes_each_side=15)
        logger.info("Subscribing strike corridor (%d tokens)...", len(corridor))
        self.ws.subscribe_tokens(corridor)

    def subscribe_symbol(self, clean_alias_or_canonical: str) -> bool:
        """Dynamically ensures a specific contract is subscribed to live ticks."""
        if not self.ws:
            return False

        token = None
        exch = "NFO"

        # Check if alias like NIFTY22500CE
        if clean_alias_or_canonical in self.contract_master._clean_alias_to_token:
            token = self.contract_master._clean_alias_to_token[clean_alias_or_canonical]
            meta = self.contract_master.get_by_token(token)
            if meta:
                exch = meta.exchange
        # Check if canonical like NIFTY|2026-10-15|22500|CE
        elif clean_alias_or_canonical in self.contract_master._by_canonical_id:
            meta = self.contract_master._by_canonical_id[clean_alias_or_canonical]
            token = meta.token
            exch = meta.exchange

        if token:
            self.ws.subscribe_tokens([(exch, token)])
            return True
        return False

    def _on_ws_connected(self) -> None:
        """Called when WebSocket handshake completes: subscribe indices immediately."""
        logger.info("Alice Blue WebSocket connected! Subscribing Index Spots...")
        index_tokens = [
            ("NSE", 26000),  # NIFTY
            ("NSE", 26009),  # BANKNIFTY
            ("BSE", 1),      # SENSEX
        ]
        self.ws.subscribe_tokens(index_tokens)

    def _on_ws_tick(self, data: dict) -> None:
        """Dispatches incoming tick to QuoteStore and DataManager."""
        try:
            token_str = data.get("tk")
            if not token_str:
                return
            token = int(token_str)
            ltp = float(data.get("lp", 0.0))
            if ltp <= 0:
                return

            # 1. Check if this is an Index Spot Tick
            if token in self._spot_token_to_und:
                und = self._spot_token_to_und[token]
                dm = self.data_managers.get(und)
                if dm:
                    now_ist = datetime.now(IST)
                    if hasattr(dm, "on_tick"):
                        dm.on_tick(ltp, volume=int(data.get("v", 0) or 0), timestamp=now_ist)
                    elif hasattr(dm, "on_nifty_tick"):
                        dm.on_nifty_tick({"ltp": ltp, "volume": int(data.get("v", 0) or 0), "timestamp": now_ist})
                if self.on_tick_hook:
                    try:
                        self.on_tick_hook()
                    except Exception as hook_err:
                        logger.debug("Error in on_tick_hook: %s", hook_err)
                return

            # 2. Option Contract Tick
            inst = self._token_to_inst.get(token)
            if not inst:
                meta = self.contract_master.get_by_token(token)
                if meta:
                    inst = Instrument(
                        underlying=meta.underlying,
                        expiry=meta.expiry,
                        strike=meta.strike,
                        option_type=meta.option_type,
                        exchange=meta.exchange,
                        fyers_symbol=meta.trading_symbol,
                        lot_size=meta.lot_size,
                        tick_size=meta.tick_size,
                    )
                    self._token_to_inst[token] = inst

            if inst:
                bid = float(data.get("bp1", ltp) or ltp)
                ask = float(data.get("sp1", ltp) or ltp)
                oi = int(data.get("oi", 0) or 0)
                vol = int(data.get("v", 0) or 0)
                prev_close = float(data.get("c", 0.0) or 0.0)

                if self.quote_store:
                    self.quote_store.update_tick(
                        canonical_id=inst.canonical_id,
                        fyers_symbol=inst.fyers_symbol,
                        ltp=ltp,
                        bid=bid,
                        ask=ask,
                        oi=oi,
                        volume=vol,
                        prev_close=prev_close,
                        source="ws",
                    )

                dm = self.data_managers.get(inst.underlying)
                if dm:
                    from src.data_manager import OptionQuote
                    quote = dm.option_chain.get(inst.clean_alias)
                    if quote is None:
                        quote = OptionQuote(symbol=inst.fyers_symbol)
                    quote.ltp = ltp
                    quote.bid = bid
                    quote.ask = ask
                    quote.oi = oi
                    quote.volume = vol
                    quote.source = "ws"
                    quote.updated_at = datetime.now(timezone.utc)
                    dm.option_chain[inst.clean_alias] = quote
                    dm.option_chain[inst.canonical_id] = quote
                    dm.option_chain[inst.fyers_symbol] = quote

            if self.on_tick_hook:
                try:
                    self.on_tick_hook()
                except Exception as hook_err:
                    logger.debug("Error in on_tick_hook: %s", hook_err)

        except Exception as e:
            logger.debug("Error processing tick: %e", e)
