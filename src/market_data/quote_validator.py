"""
Centralized QuoteValidator for Nukebox options trading platform.

Validates monotonic quote age, explicit executable side quotes (Ask for BUY, Bid for SELL),
and basis-point spread constraints. Rejects stale or synthetic prices.
"""
from collections import Counter
from enum import Enum
import threading
import time
from typing import Dict, Optional, Tuple

from src.market_data.quote_store import QuoteSnapshot


class ValidationIntent(Enum):
    NEW_ENTRY = "NEW_ENTRY"
    EXIT = "EXIT"
    EVALUATION = "EVALUATION"


class QuoteValidator:
    def __init__(
        self,
        entry_max_age_ms: float = 500.0,
        exit_max_age_ms: float = 2000.0,
        eval_max_age_ms: float = 1500.0,
        max_spread_bps: int = 800,  # 8.00%
    ):
        self.entry_max_age_ms = entry_max_age_ms
        self.exit_max_age_ms = exit_max_age_ms
        self.eval_max_age_ms = eval_max_age_ms
        self.max_spread_bps = max_spread_bps

        self._rejection_counts: Counter = Counter()
        self._total_validations = 0
        self._total_passed = 0
        self._lock = threading.RLock()

    def validate(
        self,
        snapshot: Optional[QuoteSnapshot],
        side: str,
        intent: ValidationIntent = ValidationIntent.NEW_ENTRY,
    ) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Validates quote snapshot for execution or evaluation.
        Returns: (is_valid, rejection_code, executable_price)
        """
        with self._lock:
            self._total_validations += 1

        if snapshot is None:
            self._record_rejection("REJECTED_NO_QUOTE")
            return False, "REJECTED_NO_QUOTE", None

        age_ms = (time.monotonic() - snapshot.receive_monotonic_timestamp) * 1000.0

        if intent == ValidationIntent.NEW_ENTRY:
            max_age = self.entry_max_age_ms
        elif intent == ValidationIntent.EXIT:
            max_age = self.exit_max_age_ms
        else:
            max_age = self.eval_max_age_ms

        if age_ms > max_age:
            self._record_rejection("REJECTED_STALE_QUOTE")
            return False, "REJECTED_STALE_QUOTE", None

        if snapshot.ltp is None or snapshot.ltp <= 0:
            self._record_rejection("REJECTED_INVALID_LTP")
            return False, "REJECTED_INVALID_LTP", None

        norm_side = side.strip().upper() if side else ""

        if intent == ValidationIntent.EVALUATION:
            with self._lock:
                self._total_passed += 1
            return True, None, snapshot.ltp

        if norm_side == "BUY":
            if snapshot.ask is None or snapshot.ask == 0:
                self._record_rejection("REJECTED_NO_ASK")
                return False, "REJECTED_NO_ASK", None
            if snapshot.ask < 0:
                self._record_rejection("REJECTED_INVALID_ASK")
                return False, "REJECTED_INVALID_ASK", None

            if snapshot.bid > 0:
                spread_bps = ((snapshot.ask - snapshot.bid) / snapshot.ask) * 10000.0
                if spread_bps > self.max_spread_bps:
                    self._record_rejection("REJECTED_EXCESSIVE_SPREAD")
                    return False, "REJECTED_EXCESSIVE_SPREAD", None

            with self._lock:
                self._total_passed += 1
            return True, None, snapshot.ask

        elif norm_side == "SELL":
            if snapshot.bid is None or snapshot.bid == 0:
                self._record_rejection("REJECTED_NO_BID")
                return False, "REJECTED_NO_BID", None
            if snapshot.bid < 0:
                self._record_rejection("REJECTED_INVALID_BID")
                return False, "REJECTED_INVALID_BID", None

            if snapshot.ask > 0:
                spread_bps = ((snapshot.ask - snapshot.bid) / snapshot.ask) * 10000.0
                if spread_bps > self.max_spread_bps:
                    self._record_rejection("REJECTED_EXCESSIVE_SPREAD")
                    return False, "REJECTED_EXCESSIVE_SPREAD", None

            with self._lock:
                self._total_passed += 1
            return True, None, snapshot.bid

        else:
            self._record_rejection("REJECTED_INVALID_SIDE")
            return False, "REJECTED_INVALID_SIDE", None

    def _record_rejection(self, code: str) -> None:
        with self._lock:
            self._rejection_counts[code] += 1

    def get_stats(self) -> Dict:
        with self._lock:
            return {
                "total_validations": self._total_validations,
                "total_passed": self._total_passed,
                "rejection_counts": dict(self._rejection_counts),
            }

    def reset_stats(self) -> None:
        with self._lock:
            self._rejection_counts.clear()
            self._total_validations = 0
            self._total_passed = 0
