-- Phase 8: Add order_book_snapshot column for paper-mode slippage audit
-- Stores top levels of the order book + timestamp for analyzing execution quality
-- New databases using 001_baseline.sql already have this column

ALTER TABLE signal_runs
ADD COLUMN IF NOT EXISTS order_book_snapshot JSONB;
