"""
Alice Blue Contract Master & Strike Corridor Manager
===================================================
Downloads official NFO.csv and BFO.csv daily, parses index options,
and maps clean strategy aliases (e.g. NIFTY22500CE) directly to
numeric exchange tokens without brittle regex or synthetic date math.
"""
from dataclasses import dataclass
from datetime import date, datetime
import csv
import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo
import requests

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

NFO_CSV_URL = "https://v2api.aliceblueonline.com/restpy/static/contract_master/NFO.csv"
BFO_CSV_URL = "https://v2api.aliceblueonline.com/restpy/static/contract_master/BFO.csv"

# Pre-defined index spot tokens for Alice Blue
INDEX_SPOT_TOKENS = {
    "NIFTY": ("NSE", 26000),
    "BANKNIFTY": ("NSE", 26009),
    "SENSEX": ("BSE", 1),
}

STRIKE_STEPS = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "SENSEX": 100,
}


@dataclass(frozen=True, slots=True)
class ContractMeta:
    exchange: str           # "NFO" or "BFO"
    exchange_segment: str   # "nse_fo" or "bse_fo"
    underlying: str         # "NIFTY", "BANKNIFTY", "SENSEX"
    token: int              # e.g. 44612
    strike: float           # e.g. 22500.0
    option_type: str        # "CE" or "PE"
    expiry: date            # e.g. 2026-10-15
    trading_symbol: str     # e.g. "NIFTY24OCT22500CE"
    lot_size: int           # e.g. 25, 15, 10
    tick_size: float = 0.05

    @property
    def canonical_id(self) -> str:
        k = int(self.strike) if self.strike.is_integer() else self.strike
        return f"{self.underlying}|{self.expiry.isoformat()}|{k}|{self.option_type}"

    @property
    def clean_alias(self) -> str:
        k = int(self.strike) if self.strike.is_integer() else self.strike
        return f"{self.underlying}{k}{self.option_type}"

    @property
    def noren_subscribe_key(self) -> str:
        """Returns the key format required by NorenWS e.g. 'NFO|44612' or 'BFO|1163250'."""
        return f"{self.exchange}|{self.token}"


class ContractMaster:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or (Path(__file__).resolve().parent.parent.parent / "data" / "contracts")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._by_token: Dict[int, ContractMeta] = {}
        self._by_canonical_id: Dict[str, ContractMeta] = {}
        self._clean_alias_to_token: Dict[str, int] = {}
        self._active_expiry_by_underlying: Dict[str, date] = {}
        self._contracts_by_underlying: Dict[str, List[ContractMeta]] = {
            "NIFTY": [],
            "BANKNIFTY": [],
            "SENSEX": []
        }
        self._futures_by_underlying: Dict[str, List[ContractMeta]] = {
            "NIFTY": [],
            "BANKNIFTY": [],
            "SENSEX": []
        }
        self._active_future_by_underlying: Dict[str, ContractMeta] = {}
        self._future_token_to_underlying: Dict[int, str] = {}

    def load_contracts(self, force_download: bool = False) -> None:
        """Downloads (if needed) and parses official NFO and BFO contracts into memory."""
        today_str = datetime.now(IST).strftime("%Y%m%d")
        nfo_path = self.cache_dir / f"NFO_{today_str}.csv"
        bfo_path = self.cache_dir / f"BFO_{today_str}.csv"

        # 1. Download if missing or forced
        if force_download or not nfo_path.exists():
            self._download_file(NFO_CSV_URL, nfo_path)
        if force_download or not bfo_path.exists():
            self._download_file(BFO_CSV_URL, bfo_path)

        # 2. Prune old CSV files older than 2 days to keep disk < 15 MB
        self._prune_old_csvs()

        # 3. Parse NFO and BFO files
        self._by_token.clear()
        self._by_canonical_id.clear()
        self._clean_alias_to_token.clear()
        self._contracts_by_underlying = {"NIFTY": [], "BANKNIFTY": [], "SENSEX": []}
        self._futures_by_underlying = {"NIFTY": [], "BANKNIFTY": [], "SENSEX": []}
        self._active_future_by_underlying.clear()
        self._future_token_to_underlying.clear()

        if nfo_path.exists():
            self._parse_nfo(nfo_path)
        if bfo_path.exists():
            self._parse_bfo(bfo_path)

        # 4. Resolve active (nearest weekly) expiry for each index
        today = datetime.now(IST).date()
        for und, contracts in self._contracts_by_underlying.items():
            future_expiries = sorted({c.expiry for c in contracts if c.expiry >= today})
            if future_expiries:
                active_exp = future_expiries[0]
                self._active_expiry_by_underlying[und] = active_exp
                # Map clean aliases for active expiry
                for c in contracts:
                    if c.expiry == active_exp:
                        self._clean_alias_to_token[c.clean_alias] = c.token

        # 5. Resolve active near-month Futures for each index
        for und, futs in self._futures_by_underlying.items():
            valid_futs = sorted([f for f in futs if f.expiry >= today], key=lambda x: x.expiry)
            if valid_futs:
                near_fut = valid_futs[0]
                self._active_future_by_underlying[und] = near_fut
                self._future_token_to_underlying[near_fut.token] = und

        logger.info(
            "ContractMaster loaded: %d contracts indexed. Active expiries: %s. Active futures: %s",
            len(self._by_token),
            {k: str(v) for k, v in self._active_expiry_by_underlying.items()},
            {k: f"{v.trading_symbol} (Token {v.token})" for k, v in self._active_future_by_underlying.items()}
        )

    def _download_file(self, url: str, target_path: Path) -> None:
        try:
            logger.info("Downloading contract master from %s...", url)
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            target_path.write_text(resp.text, encoding="utf-8")
            logger.info("Saved %s (%.2f MB)", target_path.name, len(resp.text) / (1024 * 1024))
        except Exception as e:
            logger.error("Failed to download contract file from %s: %s", url, e)

    def _prune_old_csvs(self) -> None:
        today_str = datetime.now(IST).strftime("%Y%m%d")
        for f in self.cache_dir.glob("*.csv"):
            if today_str not in f.name:
                try:
                    f.unlink()
                    logger.debug("Pruned stale contract file: %s", f.name)
                except Exception:
                    pass

    def _parse_nfo(self, path: Path) -> None:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = row.get("Symbol", "").strip()
                if sym not in ("NIFTY", "BANKNIFTY"):
                    continue
                itype = row.get("Instrument Type", "").strip()
                if itype not in ("OPTIDX", "FUTIDX"):
                    continue
                try:
                    token = int(row["Token"])
                    strike = float(row.get("Strike Price", 0.0) or 0.0)
                    opttype = row.get("Option Type", "").strip().upper()
                    if itype == "FUTIDX":
                        opttype = "FUT"
                        strike = 0.0
                    exp_date = date.fromisoformat(row["Expiry Date"].strip())
                    lot_size = int(row.get("Lot Size", 25))
                    meta = ContractMeta(
                        exchange="NFO",
                        exchange_segment="nse_fo",
                        underlying=sym,
                        token=token,
                        strike=strike,
                        option_type=opttype,
                        expiry=exp_date,
                        trading_symbol=row.get("Trading Symbol", "").strip(),
                        lot_size=lot_size,
                    )
                    self._by_token[token] = meta
                    self._by_canonical_id[meta.canonical_id] = meta
                    if itype == "FUTIDX":
                        self._futures_by_underlying[sym].append(meta)
                    else:
                        self._contracts_by_underlying[sym].append(meta)
                except (ValueError, KeyError):
                    continue

    def _parse_bfo(self, path: Path) -> None:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = row.get("Symbol", "").strip()
                ins_name = row.get("Instrument Name", "").strip()
                tsym = row.get("Trading Symbol", "").strip()
                if sym != "SENSEX" and "SENSEX" not in ins_name and not tsym.startswith("SENSEX"):
                    continue
                itype = row.get("Instrument Type", "").strip()
                is_future = (ins_name == "IF" or itype == "FUTIDX" or tsym.endswith("FUT"))
                try:
                    token = int(row["Token"])
                    strike = float(row.get("Strike Price", 0.0) or 0.0)
                    opttype = row.get("Option Type", "").strip().upper()
                    if is_future:
                        opttype = "FUT"
                        strike = 0.0
                    exp_date = date.fromisoformat(row["Expiry Date"].strip())
                    lot_size = int(row.get("Lot Size", 10))
                    meta = ContractMeta(
                        exchange="BFO",
                        exchange_segment="bse_fo",
                        underlying="SENSEX",
                        token=token,
                        strike=strike,
                        option_type=opttype,
                        expiry=exp_date,
                        trading_symbol=tsym,
                        lot_size=lot_size,
                    )
                    self._by_token[token] = meta
                    self._by_canonical_id[meta.canonical_id] = meta
                    if is_future:
                        self._futures_by_underlying["SENSEX"].append(meta)
                    else:
                        self._contracts_by_underlying["SENSEX"].append(meta)
                except (ValueError, KeyError):
                    continue

    def get_by_token(self, token: int) -> Optional[ContractMeta]:
        return self._by_token.get(token)

    def get_by_canonical_id(self, canonical_id: str) -> Optional[ContractMeta]:
        return self._by_canonical_id.get(canonical_id)

    def get_token_by_alias(self, alias: str) -> Optional[int]:
        """Resolves clean alias like 'NIFTY22500CE' to numeric token for current active expiry."""
        return self._clean_alias_to_token.get(alias)

    def get_active_expiry(self, underlying: str) -> Optional[date]:
        """Returns nearest weekly active expiry date for the underlying (e.g. NIFTY -> 2026-10-19)."""
        return self._active_expiry_by_underlying.get(underlying)

    def get_active_future(self, underlying: str) -> Optional[ContractMeta]:
        """Returns the ContractMeta of the active near-month future for the underlying."""
        return self._active_future_by_underlying.get(underlying)

    def get_underlying_for_future_token(self, token: int) -> Optional[str]:
        """Maps a future contract token back to its underlying ('NIFTY', 'BANKNIFTY', 'SENSEX')."""
        return self._future_token_to_underlying.get(token)

    def get_corridor_tokens(
        self,
        spot_prices: Dict[str, float],
        strikes_each_side: int = 15
    ) -> List[Tuple[str, int]]:
        """
        Returns list of (exchange, token) tuples for the full strike corridor:
        - Spot indices (NIFTY 26000, BANKNIFTY 26009, SENSEX 1)
        - Active near-month Index Futures (NIFTY-FUT, BANKNIFTY-FUT, SENSEX-FUT)
        - ATM ± strikes_each_side for active expiry (NIFTY, BANKNIFTY, SENSEX)
        Total ~192 tokens.
        """
        results: List[Tuple[str, int]] = []

        # 1. Add Index Spot tokens
        for und, (exch, tok) in INDEX_SPOT_TOKENS.items():
            results.append((exch, tok))

        # 2. Add Active Near-Month Futures tokens
        for und, fut_meta in self._active_future_by_underlying.items():
            results.append((fut_meta.exchange, fut_meta.token))

        # 3. Add Option Corridor tokens for active expiries
        for und, spot in spot_prices.items():
            if spot <= 0 or und not in self._active_expiry_by_underlying:
                continue
            step = STRIKE_STEPS.get(und, 50)
            active_exp = self._active_expiry_by_underlying[und]
            atm_strike = round(spot / step) * step

            # Select strikes in range [atm - 15*step, atm + 15*step]
            corridor_strikes = {
                atm_strike + i * step
                for i in range(-strikes_each_side, strikes_each_side + 1)
            }

            for c in self._contracts_by_underlying.get(und, []):
                if c.expiry == active_exp and c.strike in corridor_strikes:
                    results.append((c.exchange, c.token))

        return results
