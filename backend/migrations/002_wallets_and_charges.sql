-- Run once (idempotent) against the Supabase Postgres project, same as 001_options_positions.sql.
-- Adds per-leg charge tracking to closed trades, and a durable per-strategy wallet balance so
-- compounding P&L survives a backend restart (previously PaperTrader was rebuilt from scratch in
-- memory on every restart, silently discarding any wallet state -- see docs/ARCHITECTURE.md).

ALTER TABLE public.options_positions ADD COLUMN IF NOT EXISTS entry_charges numeric;
ALTER TABLE public.options_positions ADD COLUMN IF NOT EXISTS exit_charges numeric;

CREATE TABLE IF NOT EXISTS public.options_wallets (
    strategy         text PRIMARY KEY,
    balance          numeric NOT NULL,
    allocated_capital numeric NOT NULL,
    updated_at       timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.options_wallets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS options_wallets_service_only ON public.options_wallets;
CREATE POLICY options_wallets_service_only ON public.options_wallets
    USING (auth.role() = 'service_role') WITH CHECK (auth.role() = 'service_role');
