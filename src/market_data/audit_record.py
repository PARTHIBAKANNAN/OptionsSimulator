"""
ExecutionAuditRecord and AuditLogger for Nukebox options trading platform.

Records exactly 24 fields for every order execution attempt (both FILLED and REJECTED)
to maintain a complete audit trail for the 3-month paper-trading experiment.
"""
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import logging
from pathlib import Path
import threading
from typing import Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_AUDIT_DIR = PROJECT_ROOT / "data" / "market_analysis"


@dataclass(frozen=True, slots=True)
class ExecutionAuditRecord:
    # 1-5: Identification
    event_id: str                   # 1. UUID
    strategy_id: str                # 2. Strategy name
    canonical_instrument_id: str    # 3. UNDERLYING|EXPIRY|STRIKE|TYPE
    underlying: str                 # 4. "BANKNIFTY", "NIFTY", "SENSEX"
    expiry: str                     # 5. "2026-09-24"

    # 6-10: Contract Details & Order
    strike: float                   # 6. Strike price
    option_type: str                # 7. "CE" or "PE"
    fyers_symbol: str               # 8. "NSE:BANKNIFTY26SEP56000CE"
    side: str                       # 9. "BUY" or "SELL"
    quantity: int                   # 10. Order lot qty

    # 11-15: Quote Context & Versions
    ltp: float                      # 11. Live LTP
    bid: float                      # 12. Live Bid
    ask: float                      # 13. Live Ask
    decision_quote_version: int     # 14. Version when signal evaluated
    execution_quote_version: int    # 15. Version when fill executed

    # 16-20: Timestamps & Latency
    exchange_timestamp: float       # 16. Broker tick timestamp
    receive_timestamp: float        # 17. Epoch receive timestamp
    processing_timestamp: float     # 18. Epoch validator timestamp
    execution_timestamp: float      # 19. Epoch execution timestamp
    quote_age_ms: float             # 20. Monotonic quote age in ms

    # 21-24: Outcome
    execution_price: Optional[float]# 21. Ask for BUY, Bid for SELL (None if rejected)
    status: str                     # 22. "FILLED" or "REJECTED"
    rejection_code: Optional[str]   # 23. e.g. "REJECTED_NO_ASK", "REJECTED_STALE_QUOTE"
    rejection_reason: Optional[str] # 24. Detailed text description

    def to_dict(self) -> Dict:
        return asdict(self)


class AuditLogger:
    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or DEFAULT_AUDIT_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._records: List[ExecutionAuditRecord] = []
        self._lock = threading.RLock()

    def log_record(self, record: ExecutionAuditRecord) -> None:
        with self._lock:
            self._records.append(record)
            date_str = datetime.now().strftime("%Y%m%d")
            jsonl_file = self.log_dir / f"execution_audit_{date_str}.jsonl"
            try:
                with open(jsonl_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record.to_dict()) + "\n")
            except Exception as e:
                logger.error("Failed to write audit record to %s: %s", jsonl_file, e)

    def get_records(self) -> List[ExecutionAuditRecord]:
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
