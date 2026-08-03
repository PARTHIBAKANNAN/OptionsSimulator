-- Run once (idempotent) against the Supabase Postgres project. No migration framework —
-- hand-written SQL, same approach as TradeDashBoard's migrations/001_orders.sql.
-- The backend connects via one pooled service connection (not per-user JWTs), so RLS below is
-- defense-in-depth only; real isolation is app-side.

CREATE TABLE IF NOT EXISTS public.options_positions (
    order_id       text PRIMARY KEY,
    symbol         text NOT NULL,
    side           text NOT NULL,
    qty            integer NOT NULL,
    lot_size       integer NOT NULL,
    entry_price    numeric NOT NULL,
    entry_time     timestamptz NOT NULL,
    status         text NOT NULL,
    stop_loss      numeric,
    take_profit    numeric,
    strategy       text,
    exit_price     numeric,
    exit_time      timestamptz,
    exit_reason    text,
    realized_pnl   numeric,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS options_positions_status_idx ON public.options_positions (status);
CREATE INDEX IF NOT EXISTS options_positions_entry_time_idx ON public.options_positions (entry_time DESC);

CREATE TABLE IF NOT EXISTS public.options_signals (
    id             uuid PRIMARY KEY,
    strategy       text NOT NULL,
    direction      text NOT NULL,
    strike         text NOT NULL,
    confidence     numeric NOT NULL,
    rationale      text,
    entry_price    numeric NOT NULL,
    timestamp      timestamptz NOT NULL,
    status         text NOT NULL,  -- pending | approve | reject | timeout
    decided_via    text,           -- web | telegram | null (still pending)
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS options_signals_timestamp_idx ON public.options_signals (timestamp DESC);

CREATE TABLE IF NOT EXISTS public.options_daily_summary (
    trade_date       date PRIMARY KEY,
    total_trades     integer NOT NULL,
    win_rate         numeric,
    realized_pnl     numeric NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.options_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.options_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.options_daily_summary ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS options_positions_service_only ON public.options_positions;
CREATE POLICY options_positions_service_only ON public.options_positions
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS options_signals_service_only ON public.options_signals;
CREATE POLICY options_signals_service_only ON public.options_signals
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');

DROP POLICY IF EXISTS options_daily_summary_service_only ON public.options_daily_summary;
CREATE POLICY options_daily_summary_service_only ON public.options_daily_summary
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');
