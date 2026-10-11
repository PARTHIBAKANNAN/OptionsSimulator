"""
Unified Alice Blue Broker Client for OptionsSimulator
======================================================
Manages:
1. Daily 24-hr authentication (TOTP or cached user session).
2. Contract master downloads (NFO.csv / BFO.csv) and token resolution.
3. High-throughput NorenWS WebSocket streaming for Spot Indices and Option Corridor.
4. Seamless routing of live ticks directly to DataManager and QuoteStore.
"""
from datetime import date, datetime
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
        session_token: str = "",
        token_cache_path: Optional[Path] = None,
        quote_store: Optional[QuoteStore] = None,
        instrument_registry: Optional[InstrumentRegistry] = None,
        data_managers: Optional[Dict[str, any]] = None,
    ):
        self.user_id = str(user_id).strip()
        self.password = str(password).strip()
        self.totp_key = str(totp_key).strip()
        self.api_key = str(api_key).strip()
        self._user_session = str(session_token).strip()

        self.token_cache_path = token_cache_path or (
            Path(__file__).resolve().parent.parent.parent / "data" / "aliceblue_token.json"
        )
        self.quote_store = quote_store
        self.instrument_registry = instrument_registry
        self.data_managers = data_managers or {}

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

    @property
    def is_authenticated(self) -> bool:
        return bool(self._user_session and self._is_token_valid(self._user_session))

    @property
    def is_connected(self) -> bool:
        return bool(self.ws and self.ws.is_connected())

    def initialize(self) -> bool:
        """Loads cached session or logs in, loads contract master, and sets up WebSocket."""
        # 1. Authenticate / Restore Session
        if not self._restore_session():
            logger.info("No valid cached session found. Attempting login...")
            if not self.authenticate():
                logger.error("Alice Blue authentication failed.")
                return False

        # 2. Load Contract Master
        try:
            self.contract_master.load_contracts()
            self._sync_instruments_to_registry()
        except Exception as e:
            logger.error("Error loading ContractMaster: %e", e)
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
        if not self.ws:
            if not self.initialize():
                return
        if self.ws:
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
            return exp > (time.time() + 300)  # At least 5 mins remaining
        except Exception:
            return False

    def _restore_session(self) -> bool:
        if self._user_session and self._is_token_valid(self._user_session):
            return True
        if self.token_cache_path.exists():
            try:
                data = json.loads(self.token_cache_path.read_text(encoding="utf-8"))
                token = data.get("user_session", "")
                if self._is_token_valid(token):
                    self._user_session = token
                    logger.info("Restored valid Alice Blue session from %s", self.token_cache_path.name)
                    return True
            except Exception as e:
                logger.warning("Failed to restore session from cache: %e", e)
        return False

    def authenticate(self) -> bool:
        """Performs authentication or validates session."""
        if self._user_session and self._is_token_valid(self._user_session):
            self._save_session(self._user_session)
            return True
        logger.error("No active Alice Blue session token available.")
        return False

    def _save_session(self, token: str) -> None:
        try:
            self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_cache_path.write_text(
                json.dumps({"user_session": token, "updated_at": datetime.now(IST).isoformat()}),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning("Could not cache session token: %e", e)

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
                    dm.on_tick(ltp, volume=int(data.get("v", 0) or 0))
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

            if inst and self.quote_store:
                bid = float(data.get("bp1", ltp) or ltp)
                ask = float(data.get("sp1", ltp) or ltp)
                oi = int(data.get("oi", 0) or 0)
                vol = int(data.get("v", 0) or 0)
                prev_close = float(data.get("c", 0.0) or 0.0)

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

        except Exception as e:
            logger.debug("Error processing tick: %e", e)
