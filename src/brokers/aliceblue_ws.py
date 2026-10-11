"""
Alice Blue NorenWS WebSocket Client for OptionsSimulator
=========================================================
Connects to wss://ws1.aliceblueonline.com/NorenWS/
Streams tick-level data for spot indices and active strike corridor.
Zero polling, sub-50ms latency, thread-safe, and resilient auto-reconnect.
"""
from datetime import datetime
import hashlib
import json
import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo
import requests
import websocket

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

WS_URL = "wss://ws1.aliceblueonline.com/NorenWS/"
CREATE_WS_SESS_URL = "https://a3.aliceblueonline.com/open-api/od/v1/profile/createWsSess"


class AliceBlueWS:
    def __init__(
        self,
        user_id: str,
        user_session: str,
        on_tick_callback: Optional[Callable[[dict], None]] = None,
        on_connect_callback: Optional[Callable[[], None]] = None,
    ):
        self.user_id = str(user_id)
        self.user_session = str(user_session)
        self.on_tick_callback = on_tick_callback
        self.on_connect_callback = on_connect_callback

        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._connected = False
        self._handshake_done = False
        self._running = False
        self._lock = threading.RLock()

        # Track currently subscribed keys: e.g. "NSE|26000", "NFO|44612"
        self._subscribed_keys: Set[str] = set()

        # Metrics
        self.tick_count = 0
        self.last_tick_time = 0.0

    def _compute_susertoken(self) -> str:
        """Computes double SHA-256 hash of the user session JWT required by NorenWS."""
        h1 = hashlib.sha256(self.user_session.encode("utf-8")).hexdigest()
        return hashlib.sha256(h1.encode("utf-8")).hexdigest()

    def create_ws_session(self) -> bool:
        """Hits Alice Blue REST API to initialize the WebSocket session."""
        try:
            headers = {
                "Authorization": f"Bearer {self.user_session}",
                "Content-Type": "application/json"
            }
            payload = {
                "source": "API",
                "userId": self.user_id
            }
            resp = requests.post(CREATE_WS_SESS_URL, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Alice Blue createWsSess initialized successfully.")
                return True
            else:
                logger.error("createWsSess failed with status %d: %s", resp.status_code, resp.text)
                return False
        except Exception as e:
            logger.error("Error creating WS session: %e", e)
            return False

    def connect(self) -> None:
        """Starts WebSocket client in background daemon thread."""
        with self._lock:
            if self._running:
                return
            self._running = True

        # Ensure session is created with broker
        self.create_ws_session()

        self._thread = threading.Thread(target=self._run_loop, name="AliceBlueWS-Thread", daemon=True)
        self._thread.start()

    def disconnect(self) -> None:
        """Stops WebSocket and closes connection."""
        with self._lock:
            self._running = False
            self._connected = False
            self._handshake_done = False
            if self._ws:
                try:
                    self._ws.close()
                except Exception:
                    pass

    def is_connected(self) -> bool:
        return self._connected and self._handshake_done

    def subscribe_tokens(self, token_pairs: List[Tuple[str, int]]) -> None:
        """
        Subscribes to a list of (exchange, token) pairs.
        e.g. [("NSE", 26000), ("NFO", 44612), ("BSE", 1), ("BFO", 1163250)]
        """
        if not token_pairs:
            return

        new_keys = []
        with self._lock:
            for exch, tok in token_pairs:
                key = f"{exch}|{tok}"
                if key not in self._subscribed_keys:
                    self._subscribed_keys.add(key)
                    new_keys.append(key)

        if new_keys and self.is_connected():
            self._send_subscription(new_keys)

    def _send_subscription(self, keys: List[str]) -> None:
        # NorenWS takes keys joined by '#'
        # Batch in chunks of 50 to avoid overly large frame packets
        chunk_size = 50
        for i in range(0, len(keys), chunk_size):
            chunk = keys[i:i + chunk_size]
            sub_msg = {
                "k": "#".join(chunk),
                "t": "t"  # touchline / quote feed
            }
            try:
                if self._ws:
                    self._ws.send(json.dumps(sub_msg))
                    logger.debug("Subscribed chunk of %d tokens to Alice Blue WS", len(chunk))
            except Exception as e:
                logger.error("Failed to send subscription: %e", e)

    def _run_loop(self) -> None:
        susertoken = self._compute_susertoken()
        while self._running:
            try:
                def on_open(ws):
                    logger.info("Alice Blue WebSocket connected! Sending handshake...")
                    with self._lock:
                        self._connected = True
                    # Handshake message
                    init_msg = {
                        "susertoken": susertoken,
                        "t": "c",
                        "actid": f"{self.user_id}_API",
                        "uid": f"{self.user_id}_API",
                        "source": "API"
                    }
                    ws.send(json.dumps(init_msg))

                def on_message(ws, msg):
                    try:
                        data = json.loads(msg) if isinstance(msg, str) and msg.startswith("{") else msg
                    except Exception:
                        return

                    if not isinstance(data, dict):
                        return

                    # Check handshake ack
                    if data.get("t") == "ck" and data.get("s") == "OK":
                        logger.info("Alice Blue WebSocket handshake OK!")
                        with self._lock:
                            self._handshake_done = True
                        if self.on_connect_callback:
                            try:
                                self.on_connect_callback()
                            except Exception as e:
                                logger.error("Error in on_connect_callback: %e", e)

                        # Re-subscribe all registered keys
                        with self._lock:
                            all_keys = list(self._subscribed_keys)
                        if all_keys:
                            self._send_subscription(all_keys)
                        return

                    # Process market data ticks ("tk" touchline or "tf" full)
                    if data.get("t") in ("tk", "tf"):
                        self.tick_count += 1
                        self.last_tick_time = time.time()
                        if self.on_tick_callback:
                            try:
                                self.on_tick_callback(data)
                            except Exception as e:
                                logger.error("Error in on_tick_callback: %e", e)

                def on_error(ws, error):
                    logger.error("Alice Blue WebSocket error: %s", error)

                def on_close(ws, close_status, close_msg):
                    logger.warning("Alice Blue WebSocket closed: %s (code %s)", close_msg, close_status)
                    with self._lock:
                        self._connected = False
                        self._handshake_done = False

                self._ws = websocket.WebSocketApp(
                    WS_URL,
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close
                )
                self._ws.run_forever(ping_interval=15, ping_timeout=10)

            except Exception as e:
                logger.error("WebSocket run loop error: %e", e)

            if self._running:
                logger.info("Reconnecting Alice Blue WebSocket in 3 seconds...")
                time.sleep(3)
