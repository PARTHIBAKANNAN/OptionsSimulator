# NukeBox / OptionsSimulator — Remediation Plan
**Goal:** a low-latency, trustworthy **paper-trading** options engine (NIFTY / SENSEX / BANKNIFTY) that is production-shaped so flipping to live in Jan 2027 is config-only.
**Scope now:** fix the four defects below; do *not* touch order-placement (stays paper). **Target:** best achievable on Fyers' public/free WebSocket — realistically **~150–400 ms** end-to-end, not broker-internal (~50 ms). We stop *masking* latency and make any residual lag *visible and bounded*.

> This plan is grounded in a direct read of the current `main` HEAD (commit `23eb99d`, which **reverted** the 3-socket architecture back to single-socket auto-subscribe) **and live diagnostics on the production VM on 2026-10-01 during market hours**. File:line references are against that HEAD.

## 0.1 CONFIRMED on the production VM (2026-10-01, ~11:00 IST, market open)

- **Host:** 1 vCPU / 5.9 GB, load average ~2.5 (core oversubscribed ~2.5×). The single core is a real latency source — the asyncio loop competes with every CPU-bound op (deepcopy per `STREAM_INTERVAL`, pandas resample, 44-strategy eval).
- **`STREAM_INTERVAL=1.0`** on the server (broadcaster pushes once/sec) on top of the 1s main loop ⇒ ~2s baseline before network.
- **Mode is genuinely live** (`fyers_authenticated:true`), **549 symbols on the one socket** (`monitored_symbols_count:549`).
- **`SUPABASE_JWT_SECRET` is MISSING** ⇒ every `/api/auth/login` does a blocking network call to Supabase in the shared default thread pool. Confirmed amplifier for the post-market lockout (Issue 4).
- **System clock is UTC**; service sets `TZ=Asia/Kolkata` for the process only. NTP active + synchronized (so TOTP clock-skew was not today's failure — but remains a latent risk).
- **Spot lag vs Fyers REST ground truth (same instant):** NIFTY ~3.5 pts, **SENSEX ~77 pts, BANKNIFTY ~99 pts** — the less-liquid index ticks are starved on the crowded socket and freeze between updates. This *is* the "huge difference."
- **Today's signal→fill funnel:** 42 signals → **197 `REJECTED_STALE_QUOTE`** → only **18 fills**. 100% of order rejects are stale-quote: contracts don't tick within the validator's 500 ms entry bar because the socket is saturated. "App fails to take trades" and "LTP drift" are the **same** starvation root cause.
- **`/api/health/master` zeros are a bug** (reads `engine.readiness_state`/`._instruments`/`._quotes`; real attrs are `readiness_stage`/`_by_canonical_id`/`_snapshots_by_canonical`) — fix so monitoring is trustworthy.

---

## 0. Architecture as it actually is (so we fix the right thing)

- **One process, one asyncio loop.** `backend/run.py` → FastAPI (`backend/app/main.py`) lifespan starts `WebLiveEngine.start()` as a loop task + the `Broadcaster`. All HTTP/WS handlers share that loop. `systemd` keeps it always-on (`Restart=always`); there is **no** cron/timer — the "08:50 login" is an in-process check inside the engine loop.
- **Two engine classes.** `src/trader.py :: LiveTrader` is the base loop (`on_tick`, `ensure_connection_state`, the `await asyncio.sleep(1)` main loop). `backend/app/live_engine.py :: WebLiveEngine` subclasses it and owns `_publish_state()` (the thing that fills `shared_state` for the UI). **The UI is fed by `WebLiveEngine`, not `LiveTrader`.**
- **Price flow:** Fyers WS → `on_tick` (`trader.py:265`) → spot goes to `DataManager._live_ltp`; options go to `QuoteStore` (authoritative). → `_publish_state()` (`live_engine.py:60`) reads them into `shared_state` → `Broadcaster` diffs every `STREAM_INTERVAL` (0.1s) → `/ws/stream` → React.
- **Data mode switch:** `DATA_ENGINE_ENABLED`. Local `.env` is `false` ⇒ the app **replays 2 years of CSV history** and never opens a socket. **Action item 2.0: confirm the server has `DATA_ENGINE_ENABLED=true`** or everything below is moot and the "huge price gap" is literally replayed history.
- **Hard external constraint:** Fyers **free tier reliably delivers data on only ONE WebSocket**. The 3-socket design failed for this reason and was reverted. **Every fix here must live within a single socket.** The lever we have is **how many symbols we put on it** and **how we read from it**, not more sockets.

---

## Issue 4 — Post-market lockout (FIX FIRST: cheapest, highest daily pain)

**Symptom:** after close, refresh → logged out → can't log back in until the backend is restarted.

**Root cause (two stacking mechanisms, both on the shared event loop / shared thread pool):**
1. **Thread-pool starvation (the "only a restart fixes it" part).** `POST /api/auth/login` verifies the JWT via `run_in_executor(None, verify_token)` — the **default** pool (`main.py:207`). The public endpoint `/api/public/fetch-contract-candles` dispatches slow Fyers `/history` calls to the **same** default pool (`main.py:170`). Post-market those `/history` calls are slow and **rate-limited (`429 request limit reached`, confirmed in `fyersApi.log`)**; when the browser keeps requesting them they saturate the small pool, so even the instant login decode can't get a worker and hangs indefinitely.
2. **Synchronous SQLite on the loop.** `sqlite_cache.save_candles()` → `conn.executemany()` (`sqlite_candle_cache.py:74`) is called **directly on the event loop** at `live_engine.py:588, 593, 574`. A large first-flush (whole day persisted at 15:30, or the 14-day startup restore) stalls the loop, timing out every in-flight request including auth.

**Fix:**
- **4A. Dedicated, bounded executors.** Create two `ThreadPoolExecutor`s at startup: `auth_pool` (small, reserved) and `fyers_rest_pool` (bounded, e.g. 2–4 workers). Route `verify_token` to `auth_pool`, all Fyers REST (`get_historical_data`, option-chain polls, contract-candle endpoint) to `fyers_rest_pool`. Auth can never be starved by data fetches again.
- **4B. Offload SQLite writes.** Wrap every `save_candles` call in `await asyncio.to_thread(...)` (or push onto a single background writer task/queue). The loop never blocks on disk again.
- **4C. Guard the contract-candle endpoint.** `/api/public/fetch-contract-candles` must: require login, cap symbols per request, de-dupe/cache results (TTL), and apply a client-side + server-side throttle. Add a short-TTL in-memory cache so repeated post-market requests hit cache, not Fyers.
- **4D. Respect Fyers 429.** Central REST wrapper with a token-bucket rate limiter + exponential backoff on `429`/`-300`; stop silently hammering `/history`. Cache historical candles in SQLite and serve from there post-market.
- **4E. Frontend resilience.** On `/api/auth/me` timeout/401, show "reconnecting", retry with backoff, and only hard-logout on an explicit 401 (not on a timeout). Avoid a refresh storm that re-saturates the server.

**Effort:** Low. **Validates:** log in at 16:00/17:00 without restarting the backend.

---

## Issue 1 — Intermittent morning connection failure (~few days/week)

**Symptom:** some mornings the 08:50 Fyers connect doesn't establish; not every day.

**Root causes (ranked):**
- **1A. TOTP timing / VM clock skew.** `authenticate_with_totp` regenerates the code 3× with `sleep(1)` (`api_client.py:86-96`) — all within ~3s, i.e. effectively one 30s TOTP window. If the Oracle VM's clock drifts (NTP), the code is rejected *all day*; on tight-clock days it works → "fails a few days a week." Only `verify_otp` retries; `send_login_otp`/`verify_pin`/`generate_token` raise on the first transient blip.
- **1B. Stale-token "connected but dead" latch (the amplifier).** On a failed refresh, `self.access_token` keeps the **old/expired** in-memory token (only reassigned on success, `api_client.py:150`). The connect block fires because `market_open and not _connected and access_token` are all truthy, opens a socket with the dead token, and **unconditionally sets `_connected=True`** (`trader.py:465`). The staleness watchdog is gated on `_last_tick_time > 0` (`trader.py:501`) — but a dead socket never produced a tick, so `_last_tick_time` stays `0.0` and **the watchdog never fires**. Result: connected flag true, zero quotes, strategies never arm, until a later backoff refresh happens to succeed. Also the old dead `self.ws` is leaked when a late refresh re-calls `start_websocket`.
- **1C. Deploy-during-window self-sabotage.** A fresh process has `_last_login_date=None`, so the first in-window tick calls `refresh_access_token()` which **deletes a still-valid cached token** (`api_client.py:159`) and forces a TOTP re-login — converting a working session into a possible failure. `deploy.sh` only waits 40s for `fyers_authenticated`, shorter than the 30–300s login backoff.
- **1D. Timezone inconsistency.** Token cache keys on `time.strftime('%Y-%m-%d')` (system-local) while all gating uses `datetime.now(IST)` (`api_client.py:185` vs `trader.py:393`). Fragile across the UTC/IST date boundary if the VM isn't on IST.

**Fix:**
- **1A.** Ensure VM time sync (`systemd-timesync`/chrony) and `TZ=Asia/Kolkata`. Make the TOTP retry span real time windows: retry across ~2–3 distinct 30s windows with jitter; add bounded retries to **all** auth steps, not just `verify_otp`. Optionally verify local TOTP against server time drift and log a warning.
- **1B.** Treat "connected" as **proven by data, not by a flag**: only set `_connected=True` after the **first real tick** arrives within N seconds of subscribe; otherwise tear down the socket and retry. Make the watchdog fire on `_connected and (now - connect_time) > grace and active_quote_count == 0` even when `_last_tick_time == 0`. Add a real **token-validity check** (decode `exp`, or a cheap authed REST probe) instead of "string is non-empty." Close the old socket before opening a new one.
- **1C.** Don't clear a cached token that is still valid: `refresh_access_token` should keep the old token until the new one is obtained; only `_clear_token_cache()` **after** success. On a fresh process, if a valid cached token exists, use it instead of forcing TOTP.
- **1D.** Use IST consistently for the cache date.
- **1E.** Proactive morning path: attempt login at 08:50 and **keep retrying with backoff until a real tick is seen**, with a Telegram alert if not armed by, say, 09:10.

**Effort:** Medium. **Validates:** cold-start the process at 08:40 on several mornings; confirm "armed with live quotes" by 09:10 every day; simulate a bad TOTP and confirm it self-heals rather than latching.

---

## Issues 2 & 3 — Spot price gap & open-contract LTP drift (the core latency work)

These share one dominant cause: **~300 option symbols + 3 indices on a single free-tier socket**, where Fyers throttles per-symbol update frequency, so individual contracts (and sometimes the indices) tick far less than once per 15s. Then the code **masks** the gap with stale data instead of surfacing it.

### Why the prices look wrong
- **Spot (Issue 2):** `DataManager._live_ltp` is set on every index tick and **never reset** (`data_manager.py:78`). If the index tick is starved on the crowded socket, the spot price **freezes at the last value** while the market moves → large gap in fast markets. (A wrong prev-close only skews the ± change number, never the price — ruled out as the cause of the *price* gap.)
- **Open contracts (Issue 3):** `_publish_state` evicts any QuoteStore snapshot older than **15s** (`live_engine.py:63-77`), then a fallback fills the evicted symbol from `DataManager.get_option_chain()` (`live_engine.py:79-82`), which **preserves the last frozen WS LTP** (`data_manager.py:295-303`) or a ~10s-old REST price. So a starved open position shows a **frozen** price while the real option moves 10–50 pts.
- **Entry-basis mismatch (secondary):** entries fill at **ASK** (`quote_validator.py:97`, `live_engine.py:848`) but unrealized P&L marks against **LTP** → an instant phantom loss of `(ask−ltp)×qty×lot` on wide-spread strikes, independent of any feed lag. (With NIFTY lot 65, every 1 pt = ₹65/lot.)
- **Narrow:** the registry **skips contracts with `expiry=None`** (`instrument_registry.py:94-107`); a skipped contract is never subscribed → permanently frozen/REST-only.

### The clean split (why pruning is SAFE — verified on the running system)
`poll_option_chain()` (`trader.py:558-588`) already fetches the **full** option chain via REST every 10s and feeds OI/volume into `update_option_chain()` — so **OI/discovery strategies get their data from REST, not the socket.** The socket is bloated to 549 symbols purely because that same poll **auto-subscribes every discovered strike to the WS** (`trader.py:573-584`). Therefore:
- **WebSocket** carries only what needs sub-second freshness: **3 indices + ATM±N strikes + all open positions** (~60–100 symbols).
- **REST 10s poll** keeps carrying the **full chain for OI/volume discovery** (slow is fine for OI). No strategy loses data.

### Fix — within a single socket

- **3A. Drastically prune the subscribed universe (the biggest lever).** Stop auto-subscribing the full discovered chain (`trader.py:449-456`, `573-584`). Subscribe only **ATM ± ~6–8 strikes per index (~60–100 symbols)** + the 3 indices + **every open position's exact symbol (always)**. Re-center the window every few minutes as spot moves. Fewer symbols ⇒ Fyers updates each far more often ⇒ spot *and* ATM options stay fresh, and `REJECTED_STALE_QUOTE` collapses.
- **3A′. Just-in-time subscribe for edge strikes.** If a signal targets a strike outside the ATM±N window, subscribe that one symbol, wait for its first fresh tick (≤ the 500 ms validator bar), then permit entry — instead of rejecting it. This is the safety net that makes a modest N viable.
- **3B. Open positions are never pruned and never stale-substituted.** Build an `active_position_symbols` set from `paper_trader.get_positions()`. For those: (a) force-subscribe on entry, (b) in `_publish_state`/`check_exits`/EOD, **always use the last real QuoteStore WS value** (skip the 15s eviction), and (c) **never** fall back to the frozen option-chain/REST value for them. If a position's quote is genuinely stale, show the last WS price **with an age badge**, not a silently-frozen number.
- **3C. Kill the frozen-fallback masking.** Remove the "preserve last WS LTP, ignore fresh REST" behavior for display (`data_manager.py:295-303`); for non-position symbols, prefer the freshest of {WS, REST} and tag the source + age.
- **3D. Event-driven spot & position push (kill the 1s floor).** Today spot only reaches `shared_state` when the 1s main loop calls `_publish_state` (`trader.py:554`). Add a lightweight `push_spot()`/`push_position_ltp()` called directly from `on_tick` for the 3 indices and for open-position contracts — a surgical few-field `shared_state.update` that bypasses the heavy full publish. Keep the full `_publish_state` (candles/strategy rows) on a slower cadence. This removes up to ~1000 ms of avoidable lag.
- **3E. Reset stale spot.** If no index tick for > N seconds, stop presenting `_live_ltp` as current — fall back to last candle close **with an age indicator**, and let the (fixed) watchdog re-subscribe.
- **3F. Reset `_live_ltp` semantics + staleness.** Track `_live_ltp_ts`; `get_state` returns a freshness flag so the UI can badge it.
- **3G. Entry-basis consistency.** Keep fills at ask/bid (realistic for the eventual live path) but **mark open positions to mid (or LTP) consistently**, and/or display the spread explicitly so the entry "loss" isn't mistaken for a bug. This is a product decision — recommend mark-to-mid for display, keep ask/bid for fills.
- **3H. Fix the registry expiry skip.** Parse expiry from the Fyers symbol string (e.g. `...26SEP...`) as a fallback when the chain payload omits `expiry`, so no tradable contract is dropped from the subscription universe.
- **3I. Broadcaster hygiene.** `Broadcaster._run` deep-copies full `shared_state` every 100ms (`broadcaster.py:36/65`) and diffs whole nested objects; when `nifty_price` changes, the entire `positions`/`strategy_status` payload re-sends. Split a tiny `prices` channel (indices + open-position LTPs, ~tens of bytes) from the heavy state, so fast price updates don't drag the full blob or re-render all 44 strategy cards.

### Realistic latency budget after the above (single socket)
| Hop | Now | After |
|---|---|---|
| Fyers batching (pruned ~100 vs ~300 symbols) | ~500–1000 ms | ~200–400 ms |
| Main-loop `sleep(1)` before publish | 0–1000 ms | ~0 ms (event-driven push) |
| Broadcaster poll + deepcopy | 0–100 ms | ~0–50 ms (split price channel) |
| Network + React | ~100–300 ms | ~60–120 ms |
| **Total** | **~1.8–3.0 s** | **~250–500 ms**, with any residual gap shown as an age badge |

We will **not** promise broker parity — we promise *fresh-or-honest*: either a live price, or a clearly-aged one, never a silently-frozen one.

**Effort:** Medium–High. **Validates:** side-by-side vs Groww on a fast BANKNIFTY move — spot within a few points and tracking; open-position LTP tracking within a few points; no frozen numbers; age badge appears only when genuinely stale.

---

## Sequencing

| Order | Work | Why first | Effort |
|---|---|---|---|
| 1 | **Issue 4** (executors, offload SQLite, guard/rate-limit REST) | Stops the daily restart; unblocks everything else | Low |
| 2 | **2.0** Confirm server `DATA_ENGINE_ENABLED=true` + add a data-mode/staleness badge | Rules out "you're seeing replay" | Trivial |
| 3 | **Issue 1** (TOTP/clock, prove-connection-by-tick, token validity, no-nuke-cache) | Reliable live sessions | Medium |
| 4 | **Issue 3B/3H** (never-stale open positions, force-subscribe on entry, fix expiry skip) | Kills the worst LTP pain with small changes | Low–Med |
| 5 | **Issue 3A** (prune universe to ATM±N) + **3D** (event-driven push) + **2 spot** | The core latency win | Medium |
| 6 | **3C/3G/3I** (unmask fallbacks, entry-basis, split price channel) | Polish to ~250–500 ms | Med–High |

Each step is independently shippable and testable in paper mode; nothing here requires enabling live order placement.

---

## Validation strategy (paper mode)
- A `/api/health/master` already exposes readiness, monitored symbols, quote counts — extend it with **per-symbol last-tick age** and **spot freshness** so we can watch starvation directly.
- Record our spot + a couple of ATM option LTPs alongside a manual Groww reading at a few timestamps on a volatile day; chart the drift before/after each phase.
- Unit/integration: prove `verify_token` returns under load while `/history` is saturated; prove open-position LTP is never substituted by a frozen value; prove a bad TOTP self-heals.

## Open questions for you
1. Can I SSH to the VM (130.210.42.240) to confirm live `.env` (`DATA_ENGINE_ENABLED`, `SUPABASE_JWT_SECRET`), pull `journalctl -u optionssimulator-backend`, and inspect real tick-age during market hours? This would turn several "ranked hypotheses" into confirmed facts.
2. Strike-window width for pruning (±6? ±8?) — depends on how far OTM your 44 strategies ever trade. I can derive it from your trade history if unsure.
3. For display P&L: mark-to-mid, or keep LTP? (Affects how the entry spread shows up.)
