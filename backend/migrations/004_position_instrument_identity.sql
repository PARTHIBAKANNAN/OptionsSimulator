-- Run once (idempotent) against the Supabase Postgres project, same as prior migrations.
-- options_positions never persisted canonical_id/fyers_symbol, so a position that survived a
-- backend restart was restored with both fields None (Order dataclass defaults) -- it could
-- never be force-subscribed on the windowed WS feed or resolved against the QuoteStore,
-- leaving its LTP permanently unpriced after any restart. Backfill is NOT attempted here for
-- already-open legacy rows; _restore_state() re-resolves those via the clean alias at load time.

ALTER TABLE public.options_positions
    ADD COLUMN IF NOT EXISTS canonical_id text,
    ADD COLUMN IF NOT EXISTS fyers_symbol text;
