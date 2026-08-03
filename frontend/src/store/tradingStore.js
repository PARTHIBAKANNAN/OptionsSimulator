// Trade history isn't part of the live WS snapshot (it's a REST-polled list, see
// useOrders-equivalent hook usePaperTradingSync.js) — separate small store for it.
let trades = [];
let loading = true;
let error = null;

const listeners = new Set();

function emit() {
  for (const cb of listeners) cb();
}

export function setTrades(newTrades) {
  trades = newTrades;
  loading = false;
  error = null;
  emit();
}

export function setError(err) {
  error = err;
  loading = false;
  emit();
}

export function subscribe(cb) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function getSnapshot() {
  return { trades, loading, error };
}
