-- Add asset column for multi-asset (default btc). Run once for existing DBs.
-- psql "$DATABASE_URL" -f scripts/migrate_add_asset.sql

ALTER TABLE signal_runs
ADD COLUMN IF NOT EXISTS asset TEXT NOT NULL DEFAULT 'btc';
