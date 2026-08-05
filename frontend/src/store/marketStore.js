// Hand-rolled external store (no Redux) fed by WebSocket snapshot/delta frames. Consumed via
// useSyncExternalStore in src/hooks/useMarketStream.js's useMarketState().
let state = {
  nifty_price: null,
  timestamp: null,
  market_open: false,
  mode: null,
  signals: [],
  pending_signals: [],
  positions: [],
  pnl: {},
  fyers_authenticated: null,
  strategy_status: [],
};

const listeners = new Set();

function emit() {
  for (const cb of listeners) cb();
}

export function applySnapshot(data) {
  state = { ...state, ...data };
  emit();
}

export function applyDelta(changed) {
  state = { ...state, ...changed };
  emit();
}

export function subscribe(cb) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function getSnapshot() {
  return state;
}
