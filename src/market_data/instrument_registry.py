"""
Canonical Instrument Registry for Nukebox options trading platform.

Maintains official broker-provided contract metadata without synthetic expiry
assumptions or local regex reconstruction.
"""
from dataclasses import dataclass
from datetime import date, datetime
import logging
import threading
from typing import Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True, slots=True)
class Instrument:
    underlying: str
    expiry: date
    strike: float
    option_type: str
    exchange: str
    fyers_symbol: str
    lot_size: int
    tick_size: float = 0.05

    @property
    def canonical_id(self) -> str:
        k = int(self.strike) if self.strike.is_integer() else self.strike
        return f"{self.underlying}|{self.expiry.isoformat()}|{k}|{self.option_type}"

    @property
    def clean_alias(self) -> str:
        k = int(self.strike) if self.strike.is_integer() else self.strike
        return f"{self.underlying}{k}{self.option_type}"


class InstrumentRegistry:
    def __init__(self):
        self._by_canonical_id: Dict[str, Instrument] = {}
        self._by_fyers_symbol: Dict[str, Instrument] = {}
        self._clean_alias_to_canonical: Dict[str, str] = {}
        self._active_expiry_by_underlying: Dict[str, date] = {}
        self._by_underlying: Dict[str, List[Instrument]] = {}
        self._quote_store = None
        self._lock = threading.RLock()

    def set_quote_store(self, quote_store) -> None:
        """Associates QuoteStore to allow seamless canonical ID migration."""
        with self._lock:
            self._quote_store = quote_store

    def register_from_fyers_chain(
        self,
        underlying: str,
        exchange: str,
        chain_data: dict,
        lot_size: int,
    ) -> List[Instrument]:
        """
        Parses official FYERS option chain payload and registers canonical instruments.
        Zero tolerance for date.today() or local weekday/regex expiry inference.
        """
        if not chain_data or not isinstance(chain_data, dict):
            logger.warning("Empty or invalid chain_data provided for %s", underlying)
            return []

        options_chain = chain_data.get("optionsChain", [])
        expiry_data = chain_data.get("expiryData", [])

        # Extract official active expiry fallback from expiryData if needed
        fallback_expiry_date: Optional[date] = None
        if expiry_data and isinstance(expiry_data, list) and len(expiry_data) > 0:
            first_exp = expiry_data[0]
            if isinstance(first_exp, dict):
                exp_ts = first_exp.get("expiry")
                if exp_ts and isinstance(exp_ts, (int, float)) and exp_ts > 0:
                    fallback_expiry_date = datetime.fromtimestamp(exp_ts, tz=IST).date()

        registered: List[Instrument] = []

        with self._lock:
            for item in options_chain:
                if not isinstance(item, dict):
                    continue

                symbol = item.get("symbol")
                strike_price = item.get("strike_price")
                opt_type = item.get("option_type")
                raw_expiry = item.get("expiry")

                # Parse official expiry date from epoch seconds
                expiry_dt: Optional[date] = None
                if raw_expiry and isinstance(raw_expiry, (int, float)) and raw_expiry > 0:
                    expiry_dt = datetime.fromtimestamp(raw_expiry, tz=IST).date()
                elif fallback_expiry_date is not None:
                    expiry_dt = fallback_expiry_date

                # Strict validation: reject if any mandatory field is missing or invalid
                if not symbol or strike_price is None or not opt_type or expiry_dt is None:
                    logger.error(
                        "Skipping invalid contract in chain: symbol=%s, strike=%s, type=%s, expiry=%s",
                        symbol, strike_price, opt_type, expiry_dt
                    )
                    continue

                try:
                    strike_val = float(strike_price)
                except (ValueError, TypeError):
                    logger.error("Invalid strike price: %s", strike_price)
                    continue

                norm_opt_type = str(opt_type).strip().upper()
                if norm_opt_type not in ("CE", "PE"):
                    logger.error("Invalid option type: %s", opt_type)
                    continue

                instrument = Instrument(
                    underlying=underlying.upper(),
                    expiry=expiry_dt,
                    strike=strike_val,
                    option_type=norm_opt_type,
                    exchange=exchange.upper(),
                    fyers_symbol=symbol.strip(),
                    lot_size=lot_size,
                )

                # Clean up any orphaned ad-hoc registration for this symbol with a different canonical_id
                old_inst = self._by_fyers_symbol.get(instrument.fyers_symbol)
                if old_inst and old_inst.canonical_id != instrument.canonical_id:
                    self._by_canonical_id.pop(old_inst.canonical_id, None)
                    if self._quote_store:
                        self._quote_store.remap_canonical_id(old_inst.canonical_id, instrument.canonical_id)

                # Store by canonical ID and official broker symbol
                self._by_canonical_id[instrument.canonical_id] = instrument
                self._by_fyers_symbol[instrument.fyers_symbol] = instrument

                registered.append(instrument)

            # Determine active expiry: earliest valid expiry on or after today (IST).
            # If all are in the past (e.g. historical tests/fixtures), pick earliest available in registered set.
            today = datetime.now(IST).date()
            future_expiries = [inst.expiry for inst in registered if inst.expiry >= today]
            if future_expiries:
                active_exp = min(future_expiries)
            elif registered:
                active_exp = min(inst.expiry for inst in registered)
            else:
                active_exp = None

            if active_exp:
                self._active_expiry_by_underlying[underlying.upper()] = active_exp

            # Deduplicate and maintain _by_underlying
            existing_for_underlying = {inst.canonical_id: inst for inst in self._by_underlying.get(underlying.upper(), [])}
            for inst in registered:
                existing_for_underlying[inst.canonical_id] = inst
            self._by_underlying[underlying.upper()] = list(existing_for_underlying.values())

            # Re-index clean aliases to strictly map to active expiry contracts
            if active_exp:
                for inst in self._by_underlying.get(underlying.upper(), []):
                    if inst.expiry == active_exp:
                        self._clean_alias_to_canonical[inst.clean_alias] = inst.canonical_id

        logger.info(
            "Registered %d official contracts for %s (Active Expiry: %s)",
            len(registered),
            underlying,
            self._active_expiry_by_underlying.get(underlying.upper()),
        )
        return registered

    def resolve_canonical(self, canonical_id: str) -> Optional[Instrument]:
        with self._lock:
            return self._by_canonical_id.get(canonical_id)

    def resolve_by_symbol(self, fyers_symbol: str) -> Optional[Instrument]:
        with self._lock:
            return self._by_fyers_symbol.get(fyers_symbol)

    def resolve_by_clean_alias(self, clean_alias: str, underlying: Optional[str] = None) -> Optional[Instrument]:
        """
        Resolves clean alias (e.g. 'BANKNIFTY56000CE') to canonical Instrument
        for the active official expiry.
        """
        with self._lock:
            canonical_id = self._clean_alias_to_canonical.get(clean_alias)
            if canonical_id:
                return self._by_canonical_id.get(canonical_id)
            return None

    def get_active_expiry(self, underlying: str) -> Optional[date]:
        with self._lock:
            return self._active_expiry_by_underlying.get(underlying.upper())

    def get_all_instruments(self) -> List[Instrument]:
        with self._lock:
            return list(self._by_canonical_id.values())

    def get_instruments_for_underlying(self, underlying: str) -> List[Instrument]:
        with self._lock:
            return list(self._by_underlying.get(underlying.upper(), []))

    def verify_strategy_coverage(
        self,
        underlying: str,
        spot_price: float,
        strike_step: int,
        depth: int = 15,
    ) -> Tuple[bool, List[float], List[float]]:
        """
        Verifies that all strikes within +/- depth steps of ATM are registered
        for both CE and PE in the active official expiry.

        Returns (is_covered, missing_ce_strikes, missing_pe_strikes).
        """
        with self._lock:
            active_exp = self._active_expiry_by_underlying.get(underlying.upper())
            if not active_exp:
                logger.warning("Coverage check failed: No active expiry for %s", underlying)
                return False, [], []

            atm_strike = round(spot_price / strike_step) * strike_step
            required_strikes = [
                float(atm_strike + i * strike_step)
                for i in range(-depth, depth + 1)
            ]

            registered_ce_strikes: Set[float] = set()
            registered_pe_strikes: Set[float] = set()

            for inst in self._by_underlying.get(underlying.upper(), []):
                if inst.expiry == active_exp:
                    if inst.option_type == "CE":
                        registered_ce_strikes.add(inst.strike)
                    elif inst.option_type == "PE":
                        registered_pe_strikes.add(inst.strike)

            missing_ce = [k for k in required_strikes if k not in registered_ce_strikes]
            missing_pe = [k for k in required_strikes if k not in registered_pe_strikes]

            is_covered = (len(missing_ce) == 0 and len(missing_pe) == 0)
            return is_covered, missing_ce, missing_pe

    def clear(self) -> None:
        with self._lock:
            self._by_canonical_id.clear( )
            self._by_fyers_symbol.clear()
            self._clean_alias_to_canonical.clear()
            self._active_expiry_by_underlying.clear()
            self._by_underlying.clear()
