// Manages the single WebSocket connection: exponential-backoff reconnect, a staleness watchdog
// (closes+reconnects if nothing arrives for 30s), and sequence-gap detection (asks for a fresh
// snapshot if a delta arrives out of order). Ref-counted so multiple mounted components share one
// socket instead of each opening their own.
import { useEffect, useSyncExternalStore } from "react";
import { applyDelta, applySnapshot, getSnapshot, subscribe } from "../store/marketStore";
import { API_BASE } from "../lib/apiBase";

const HEARTBEAT_TIMEOUT_MS = 30_000;
const BACKOFF_START_MS = 500;
const BACKOFF_MAX_MS = 10_000;

let ws = null;
let refCount = 0;
let backoffMs = BACKOFF_START_MS;
let reconnectTimer = null;
let heartbeatTimer = null;
let lastSeq = 0;

function wsUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${API_BASE}/ws/stream`;
}

function armHeartbeat() {
  clearTimeout(heartbeatTimer);
  heartbeatTimer = setTimeout(() => {
    ws?.close();
  }, HEARTBEAT_TIMEOUT_MS);
}

function scheduleReconnect() {
  if (refCount <= 0) return;
  clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(connect, backoffMs);
  backoffMs = Math.min(backoffMs * 2, BACKOFF_MAX_MS);
}

function connect() {
  if (refCount <= 0 || ws) return;
  ws = new WebSocket(wsUrl());

  ws.onopen = () => {
    backoffMs = BACKOFF_START_MS;
    armHeartbeat();
  };

  ws.onmessage = (event) => {
    armHeartbeat();
    const frame = JSON.parse(event.data);
    if (frame.type === "snapshot") {
      lastSeq = frame.seq;
      applySnapshot(frame.data);
    } else if (frame.type === "delta") {
      if (frame.seq !== lastSeq + 1) {
        ws?.send(JSON.stringify({ type: "resync" }));
      }
      lastSeq = frame.seq;
      applyDelta(frame.data);
    } else if (frame.type === "heartbeat") {
      lastSeq = frame.seq;
    }
  };

  ws.onclose = () => {
    clearTimeout(heartbeatTimer);
    ws = null;
    scheduleReconnect();
  };

  ws.onerror = () => {
    ws?.close();
  };
}

function acquire() {
  refCount += 1;
  if (refCount === 1) connect();
}

function release() {
  refCount = Math.max(0, refCount - 1);
  if (refCount === 0) {
    clearTimeout(reconnectTimer);
    clearTimeout(heartbeatTimer);
    ws?.close();
    ws = null;
  }
}

/** Call once near the root (e.g. App.jsx) to own the WS connection's lifecycle. */
export function useMarketStream() {
  useEffect(() => {
    acquire();
    return release;
  }, []);
}

/** Call from any component that just wants to read the current live state. */
export function useMarketState() {
  return useSyncExternalStore(subscribe, getSnapshot);
}
