"""Structured logging: separate rotating log files for trades, signals, errors, and websocket events."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


def _make_logger(name: str, filename: str) -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = RotatingFileHandler(LOG_DIR / filename, maxBytes=5_000_000, backupCount=3)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger


class Logger:
    """Facade over four topic-specific loggers (trades, signals, errors, websocket)."""

    def __init__(self):
        self._trades = _make_logger("trades", "trades.log")
        self._signals = _make_logger("signals", "signals.log")
        self._errors = _make_logger("errors", "errors.log")
        self._websocket = _make_logger("websocket", "websocket.log")

    def log_signal(self, strategy: str, signal: dict) -> None:
        self._signals.info(f"[{strategy}] {signal}")

    def log_trade(self, trade) -> None:
        self._trades.info(f"{trade}")

    def log_error(self, error: str, context: dict = None) -> None:
        self._errors.error(f"{error} | context={context or {}}")

    def log_websocket_event(self, event: str, data: dict = None) -> None:
        self._websocket.info(f"{event} | {data or {}}")


_default_logger = None


def get_logger() -> Logger:
    global _default_logger
    if _default_logger is None:
        _default_logger = Logger()
    return _default_logger
