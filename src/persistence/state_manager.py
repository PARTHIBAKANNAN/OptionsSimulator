"""Persists positions/trade history to disk so a restart doesn't lose state mid-session."""
import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
POSITIONS_PATH = DATA_DIR / "positions.json"
TRADES_CSV_PATH = DATA_DIR / "trade_history.csv"
DAILY_SUMMARY_PATH = DATA_DIR / "daily_summary.json"

TRADE_FIELDS = ["order_id", "symbol", "side", "qty", "lot_size", "entry_price", "entry_time",
                "status", "stop_loss", "take_profit", "strategy", "exit_price", "exit_time",
                "exit_reason", "realized_pnl"]


def _serialize(order) -> dict:
    row = asdict(order)
    for key in ("entry_time", "exit_time"):
        if row.get(key) is not None and isinstance(row[key], datetime):
            row[key] = row[key].isoformat()
    return row


class StateManager:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save_positions(self, positions: list) -> None:
        path = self.data_dir / "positions.json"
        path.write_text(json.dumps([_serialize(p) for p in positions], indent=2))

    def load_positions(self) -> list[dict]:
        path = self.data_dir / "positions.json"
        if not path.exists():
            return []
        return json.loads(path.read_text())

    def append_trade(self, trade) -> None:
        path = self.data_dir / "trade_history.csv"
        is_new = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=TRADE_FIELDS)
            if is_new:
                writer.writeheader()
            writer.writerow(_serialize(trade))

    def get_trade_history(self):
        import pandas as pd
        path = self.data_dir / "trade_history.csv"
        if not path.exists():
            return pd.DataFrame(columns=TRADE_FIELDS)
        return pd.read_csv(path)

    def save_daily_summary(self, summary: dict) -> None:
        path = self.data_dir / "daily_summary.json"
        history = json.loads(path.read_text()) if path.exists() else []
        history.append({**summary, "date": datetime.now().strftime("%Y-%m-%d")})
        path.write_text(json.dumps(history, indent=2))
