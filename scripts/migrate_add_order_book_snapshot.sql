-- Add order_book_snapshot column for paper-mode slippage audit (Phase 8).
-- Run once: psql "$DATABASE_URL" -f scripts/migrate_add_order_book_snapshot.sql

ALTER TABLE signal_runs
ADD COLUMN IF NOT EXISTS order_book_snapshot JSONB;
