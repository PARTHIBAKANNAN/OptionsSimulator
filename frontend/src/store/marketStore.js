import { soundEngine } from "../utils/audioAlerts";

// Hand-rolled external store (no Redux) fed by WebSocket snapshot/delta frames. Consumed via
// useSyncExternalStore in src/hooks/useMarketStream.js's useMarketState().
let state = {
  nifty_price: null,
  nifty_prev_close: null,
  nifty_change: null,
  nifty_change_pct: null,
  nifty_sparkline: [],
  timestamp: null,
  market_open: false,
  exchange_open: false,
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

let prevPositionsCount = 0;

export function applySnapshot(data) {
  const newPositionsCount = (data.positions || []).length;
  if (prevPositionsCount > 0 && newPositionsCount > prevPositionsCount) {
    soundEngine.playOrderEntry();
  } else if (prevPositionsCount > 0 && newPositionsCount < prevPositionsCount) {
    soundEngine.playTargetExit();
  }
  prevPositionsCount = newPositionsCount;
  state = { ...state, ...data };
  emit();
}

export function applyDelta(changed) {
  if (changed.positions != null) {
    const newPositionsCount = changed.positions.length;
    if (newPositionsCount > prevPositionsCount) {
      soundEngine.playOrderEntry();
    } else if (newPositionsCount < prevPositionsCount) {
      soundEngine.playTargetExit();
    }
    prevPositionsCount = newPositionsCount;
  }
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
