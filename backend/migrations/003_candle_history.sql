-- Run once (idempotent) against the Supabase Postgres project, same as prior migrations.
-- Persists completed 1-min candles (OHLCV + tick-rule cumulative delta) per index, so today's
-- intraday chart/CVD history survives a backend restart instead of resetting to empty -- mirrors
-- TradeDashBoard's candle_history table, at OptionsSimulator's own 1-min-native granularity
-- (its DataManager already closes a candle every minute; 5-min chart bars are resampled from
-- these on read, both live and after a DB restore -- see docs/ARCHITECTURE.md).

CREATE TABLE IF NOT EXISTS public.options_candle_history (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    underlying     text NOT NULL,  -- 'NIFTY' or 'SENSEX'
    bucket_date    date NOT NULL,
    bucket_minute  int NOT NULL,   -- minutes since midnight IST, 1-min aligned
    open           numeric(18, 4),
    high           numeric(18, 4),
    low            numeric(18, 4),
    close          numeric(18, 4),
    volume         numeric(18, 2),
    delta          numeric(18, 2),
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (underlying, bucket_date, bucket_minute)
);

CREATE INDEX IF NOT EXISTS options_candle_history_underlying_date_idx
    ON public.options_candle_history (underlying, bucket_date);

ALTER TABLE public.options_candle_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS options_candle_history_service_only ON public.options_candle_history;
CREATE POLICY options_candle_history_service_only ON public.options_candle_history
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');
