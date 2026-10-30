import { soundEngine } from "../utils/audioAlerts";

// Hand-rolled external store (no Redux) fed by WebSocket snapshot/delta frames. Consumed via
// useSyncExternalStore in src/hooks/useMarketStream.js.
let state = {
  nifty_price: null,
  nifty_prev_close: null,
  nifty_change: null,
  nifty_change_pct: null,
  nifty_sparkline: [],
  sensex_price: null,
  sensex_prev_close: null,
  sensex_change: null,
  sensex_change_pct: null,
  banknifty_price: null,
  banknifty_prev_close: null,
  banknifty_change: null,
  banknifty_change_pct: null,
  timestamp: null,
  market_open: false,
  exchange_open: false,
  mode: null,
  signals: [],
  pending_signals: [],
  positions: [],
  pnl: {},
  aliceblue_authenticated: null,
  broker_authenticated: null,
  fyers_authenticated: null,
  strategy_status: [],
};

const fullListeners = new Set();
const spotListeners = new Set();
const strategyListeners = new Set();

let prevPositionsCount = 0;

export function applySnapshot(data) {
  const newPositionsCount = (data.positions || []).length;
  if (prevPositionsCount > 0 && newPositionsCount > prevPositionsCount) {
    soundEngine.playOrderEntry();
  } else if (prevPositionsCount > 0 && newPositionsCount < prevPositionsCount) {
    const lastExitReason = data.last_closed_trade?.exit_reason || "";
    if (lastExitReason.toUpperCase().includes("STOP") || lastExitReason.toUpperCase().includes("SL")) {
      soundEngine.playStopLossHit();
    } else {
      soundEngine.playTargetHit();
    }
  }
  prevPositionsCount = newPositionsCount;
  state = { ...state, ...data };

  // Notify all listener groups on full snapshot
  for (const cb of fullListeners) cb();
  for (const cb of spotListeners) cb();
  for (const cb of strategyListeners) cb();
}

const SPOT_KEYS = new Set([
  "nifty_price", "nifty_prev_close", "nifty_change", "nifty_change_pct",
  "sensex_price", "sensex_prev_close", "sensex_change", "sensex_change_pct",
  "banknifty_price", "banknifty_prev_close", "banknifty_change", "banknifty_change_pct",
  "timestamp", "market_open", "exchange_open", "is_connected", "corridor_subscribed",
  "ws_latency_ms", "active_quotes_count", "aliceblue_authenticated", "broker_authenticated",
  "fyers_authenticated"
]);

export function applyDelta(changed) {
  if (changed.positions != null) {
    const newPositionsCount = changed.positions.length;
    if (newPositionsCount > prevPositionsCount) {
      soundEngine.playOrderEntry();
    } else if (newPositionsCount < prevPositionsCount) {
      const lastExitReason = changed.last_closed_trade?.exit_reason || "";
      if (lastExitReason.toUpperCase().includes("STOP") || lastExitReason.toUpperCase().includes("SL")) {
        soundEngine.playStopLossHit();
      } else {
        soundEngine.playTargetHit();
      }
    }
    prevPositionsCount = newPositionsCount;
  }

  state = { ...state, ...changed };

  let hasSpotChanges = false;
  let hasStrategyChanges = false;

  for (const key of Object.keys(changed)) {
    if (SPOT_KEYS.has(key)) hasSpotChanges = true;
    if (
      key === "strategy_status" ||
      key === "pending_signals" ||
      key === "signals" ||
      key === "positions" ||
      key === "pnl"
    ) {
      hasStrategyChanges = true;
    }
  }

  // Selective fine-grained dispatch
  if (hasSpotChanges) {
    for (const cb of spotListeners) cb();
  }
  if (hasStrategyChanges) {
    for (const cb of strategyListeners) cb();
  }

  // Full backward-compatible dispatch
  for (const cb of fullListeners) cb();
}

export function subscribe(cb) {
  fullListeners.add(cb);
  return () => fullListeners.delete(cb);
}

export function subscribeSpot(cb) {
  spotListeners.add(cb);
  return () => spotListeners.delete(cb);
}

export function subscribeStrategy(cb) {
  strategyListeners.add(cb);
  return () => strategyListeners.delete(cb);
}

export function getSnapshot() {
  return state;
}

// Cached selector snapshots ensure referential stability so React doesn't trigger spurious re-renders
let cachedSpot = {};
export function getSpotSnapshot() {
  if (
    cachedSpot.nifty_price !== state.nifty_price ||
    cachedSpot.banknifty_price !== state.banknifty_price ||
    cachedSpot.sensex_price !== state.sensex_price ||
    cachedSpot.timestamp !== state.timestamp ||
    cachedSpot.ws_latency_ms !== state.ws_latency_ms ||
    cachedSpot.is_connected !== state.is_connected
  ) {
    cachedSpot = {
      nifty_price: state.nifty_price,
      nifty_prev_close: state.nifty_prev_close,
      nifty_change: state.nifty_change,
      nifty_change_pct: state.nifty_change_pct,
      sensex_price: state.sensex_price,
      sensex_prev_close: state.sensex_prev_close,
      sensex_change: state.sensex_change,
      sensex_change_pct: state.sensex_change_pct,
      banknifty_price: state.banknifty_price,
      banknifty_prev_close: state.banknifty_prev_close,
      banknifty_change: state.banknifty_change,
      banknifty_change_pct: state.banknifty_change_pct,
      timestamp: state.timestamp,
      market_open: state.market_open,
      exchange_open: state.exchange_open,
      mode: state.mode,
      is_connected: state.is_connected,
      corridor_subscribed: state.corridor_subscribed,
      ws_latency_ms: state.ws_latency_ms,
      active_quotes_count: state.active_quotes_count,
      aliceblue_authenticated: state.aliceblue_authenticated,
      broker_authenticated: state.broker_authenticated,
      fyers_authenticated: state.fyers_authenticated,
    };
  }
  return cachedSpot;
}

let cachedStrategy = {};
export function getStrategySnapshot() {
  if (
    cachedStrategy.strategy_status !== state.strategy_status ||
    cachedStrategy.pending_signals !== state.pending_signals ||
    cachedStrategy.positions !== state.positions ||
    cachedStrategy.pnl !== state.pnl
  ) {
    cachedStrategy = {
      strategy_status: state.strategy_status,
      pending_signals: state.pending_signals,
      signals: state.signals,
      positions: state.positions,
      pnl: state.pnl,
    };
  }
  return cachedStrategy;
}
