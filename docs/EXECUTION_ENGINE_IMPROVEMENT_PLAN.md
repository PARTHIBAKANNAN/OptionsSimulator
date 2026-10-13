# Execution Engine & Infrastructure Overhaul: Architectural Plan

## 1. Executive Summary & Objective

**Primary Objective:** Transform the OptionsSimulator execution engine from an error-prone, quote-lagged prototype into an institutional-grade, zero-distortion paper trading engine running sustainably on a 1 vCPU cloud instance.

**Fundamental Ground Rule:** 
* **Zero changes to core strategy rules or Stop Loss definitions.** Strategy rules and stop losses remain strictly untouched until the machine records 100% verified, clean market data.
* **The Machine is repaired first.** All upgrades target data freshness, bid/ask fills, database concurrency, and UI transparency.

---

## 2. Detailed Improvement Pillars: Benefits vs. Side Effects Matrix

---

### Pillar 1: High-Frequency Quote Engine & Stale-Tick Rejection

#### What We Are Doing
1. **Direct Binary WebSocket Stream:** Subscribe all active ATM/ITM option strikes directly via Alice Blue's binary WebSocket feed (50–150ms tick interval).
2. **True Bid/Ask Fill Simulation:** 
   * `BUY` orders fill strictly at `Best Ask` (or `LTP + 0.05` if book depth is flat).
   * `SELL` orders fill strictly at `Best Bid` (or `LTP - 0.05`).
3. **Hard Stale-Quote Circuit Breaker:**
   * If an incoming option tick is older than **1,500 milliseconds (1.5 seconds)** from the exchange timestamp, or if no tick has arrived for that contract in 3 seconds, order execution is **rejected immediately**.
   * Under no circumstances will the engine "estimate" or "invent" a synthetic option price.

#### What It Improves
* **Elimination of Distorted Trades:** Completely wipes out the 75.4% rate of distorted trade fills where entries/exits occurred outside the actual candle range.
* **Realistic Slippage Measurement:** Captures true market friction rather than idealized mid-price fills.

#### Potential Side Effects & Drawbacks
1. **Fewer Triggered Trades (Missed Entries):**
   * *The Risk:* On sudden high-volatility spikes (e.g., Budget/RBI policy or 09:15 open), if a contract's WebSocket tick is delayed by >1.5s, the engine will drop the entry signal.
   * *Mitigation:* A logged warning `[STALE_TICK_REJECTED: Symbol X, Age: 2.1s]` will notify the dashboard immediately so you know why the trade was skipped instead of taking a bad fill.
2. **Subscription Limit Overhead:**
   * *The Risk:* Alice Blue limits active WebSocket subscriptions to 250–500 tokens per connection. Tracking all 44 strategies across multiple strikes could exceed broker limits if not pruned.
   * *Mitigation:* Dynamic Strike Subscription Manager that subscribes only to ATM ± 2 strikes for active indices and unregisters far OTM strikes every 15 minutes.

---

### Pillar 2: SQLite Write-Ahead Logging (WAL) Storage Engine

#### What We Are Doing
1. **Deprecate Unprotected JSON/CSV File Overwrites:** Migrate active state (`positions.json`, `trade_history.csv`) to an ACID-compliant SQLite database (`data/simulator.db`).
2. **Enable WAL Mode (`PRAGMA journal_mode = WAL;`):**
   * Readers (FastAPI endpoints, frontend polling) read from the database without acquiring table locks.
   * Writers (Engine logging trades and candles) append transactions to the WAL log without blocking readers.
3. **Synchronous Normal Mode (`PRAGMA synchronous = NORMAL;`):**
   * Reduces disk I/O operations by 80%, critical for cloud VMs with IOPS caps.

#### What It Improves
* **Zero Database Lockups:** Completely eliminates `sqlite3.OperationalError: database is locked` and FastAPI 500 crashes during high-frequency candle updates.
* **Crash-Proof State Recovery:** If the VM reboots or the process terminates abruptly, SQLite automatically recovers from the WAL log on the next startup. No 0-byte corrupted JSON files.
* **Instant Historical Queries:** Complex queries (e.g., 44-strategy win rates, daily gross vs. charges) execute in sub-millisecond time.

#### Potential Side Effects & Drawbacks
1. **Accumulation of `-wal` and `-shm` Files on Disk:**
   * *The Risk:* If SQLite does not run a checkpoint, the WAL file can grow over several days to hundreds of megabytes.
   * *Mitigation:* Implement an automated market-close checkpoint (`PRAGMA wal_checkpoint(TRUNCATE);`) at 15:35 IST daily.
2. **Migration Transition Risk:**
   * *The Risk:* Discrepancies if legacy scripts attempt to read `trade_history.csv`.
   * *Mitigation:* Dual-write compatibility layer: the engine writes to SQLite as primary, and exports a backward-compatible `trade_history.csv` on trade close.

---

### Pillar 3: Single-Process Async Concurrency on 1 vCPU VM

#### What We Are Doing
1. **Cooperative `asyncio` Event Loop (Single Process):**
   * Run the Alice Blue WebSocket receiver, tick distributor, and strategy candle evaluator within Python’s single-threaded asynchronous event loop (`asyncio`).
2. **Zero Heavy OS Thread Creation:**
   * Do not spawn competing background operating system threads for market evaluation.
3. **1-Minute Candle Triggering:**
   * Strategy indicator evaluation runs strictly at the boundary of a closed 1-minute candle (e.g., 09:16:00, 09:17:00), never on every individual microsecond tick.

#### What It Improves
* **No CPU Starvation on 1 vCPU:** Context-switching overhead drops to zero. CPU usage remains below 15–20% on a free-tier single-core VM.
* **Sub-Millisecond Order Routing:** Ticks are processed in memory in microseconds.

#### Potential Side Effects & Drawbacks
1. **Event Loop Blocking Risk:**
   * *The Risk:* If a strategy calculation or external network call (e.g., HTTP request to Telegram or broker API) blocks synchronously for 500ms, it halts the entire event loop, delaying WebSocket tick ingestion.
   * *Mitigation:* All external HTTP calls must use `httpx.AsyncClient` or `aiohttp`. All heavy mathematical calculations must be executed via `asyncio.to_thread` with explicit timeout guards (max 50ms).

---

### Pillar 4: Pre-Market & External Intelligence Engine

#### What We Are Doing
1. **Authentic GIFT Nifty Feed:**
   * Replace the synthetic calculation (`Nifty Close - 17.0`) with live GIFT Nifty quotes sourced via Alice Blue global/index tokens or verified financial APIs.
2. **Gemini API Structured Output:**
   * Add prompt engineering and JSON validation for the Gemini Flash pre-market summary to prevent parse failures.
3. **FII / DII Flow Ingestion:**
   * Pull official daily NSE cash market provisional figures after 18:30 IST.

#### What It Improves
* **Reliable Morning Bias:** Pre-market briefing reflects real global and institutional sentiment rather than hardcoded mock figures.

#### Potential Side Effects & Drawbacks
1. **Third-Party API Rate Limits / Downtime:**
   * *The Risk:* Gemini API or external scrapers may fail due to network timeouts or rate limits.
   * *Mitigation:* Graceful fallback with cached intelligence. If Gemini API is unreachable, the dashboard displays `"Pre-Market Summary: Data unavailable (API Timeout)"` without crashing the core trading engine.

---

### Pillar 5: Animated Desktop & Mobile UI/UX Overhaul

#### What We Are Doing
1. **44-Strategy Interactive Leaderboard:**
   * Top 3 Alpha strategies highlighted with dynamic accents; laggards clearly flagged.
   * Live daily trade consumption counter per strategy: `[🟢 0/2]`, `[🟡 1/2]`, `[🔴 2/2 Capped]`.
2. **Detailed Financial & Fee Breakdown:**
   * Prominently display: `Gross Market P&L`, `Statutory Charges & Taxes (STT/GST/Turnover)`, and `Net Realized P&L`.
3. **Execution Latency & Health Gauge:**
   * Live status indicator: `Alice Blue WS: 🟢 Connected (62ms) | Active Quotes: 124 | Clock Drift: 0.04s`.
4. **Mobile & PWA Responsive Experience:**
   * Swipeable summary cards, touch-optimized typography, and instant reconnection on device wake-up (`visibilitychange`).

#### What It Improves
* **Complete Transparency:** Eliminates confusion over why an account is down (clearly showing fee drag vs. market moves).
* **Flawless Mobile Monitoring:** Allows real-time tracking from a phone browser without UI breakages.

#### Potential Side Effects & Drawbacks
1. **Frontend Memory & Battery Consumption:**
   * *The Risk:* High-frequency WebSocket updates streaming to a mobile browser can drain battery and cause UI jank.
   * *Mitigation:* UI state throttled at 250ms (4 updates/sec) via React `useDeferredValue` and batching. Background tabs pause DOM rendering when inactive.

---

## 3. Implementation Phasing & Safety Protocols

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 PHASED ROLLOUT ROADMAP                                  │
├────────────────────────────────────────┬────────────────────────────────────────────────┤
│ Phase 1: Machine Core (Days 1–2)       │ • Deploy SQLite WAL storage                    │
│                                        │ • Implement Alice Blue Ask/Bid execution logic │
│                                        │ • Deploy 1.5s Stale-Quote rejection gate       │
├────────────────────────────────────────┼────────────────────────────────────────────────┤
│ Phase 2: Intelligence & UI (Days 3–4)  │ • Deploy Animated 44-Strategy Leaderboard      │
│                                        │ • Add Mobile PWA responsiveness & Fee Split   │
│                                        │ • Connect live GIFT Nifty & Gemini API feeds   │
├────────────────────────────────────────┼────────────────────────────────────────────────┤
│ Phase 3: 30-Day Clean Burn-in          │ • Run paper engine across all 44 strategies   │
│                                        │ • Daily automated audit (0% Distorted Target)  │
│                                        │ • Mathematical selection of Top Strategies     │
└────────────────────────────────────────┴────────────────────────────────────────────────┘
```

## 4. Summary of Guarantees

1. **Strategy Integrity:** No strategy entry/exit/stop-loss logic is touched.
2. **Hardware Safety:** Single-thread async design guarantees no CPU overload on the 1 vCPU instance.
3. **Data Authenticity:** Every trade recorded going forward is backed by verified exchange timestamps and live top-of-book quotes.
