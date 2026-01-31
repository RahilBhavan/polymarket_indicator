-- Add asset column for multi-asset support (default: btc)
-- This migration is for existing databases that were created before multi-asset support
-- New databases using 001_baseline.sql already have this column

ALTER TABLE signal_runs
ADD COLUMN IF NOT EXISTS asset TEXT NOT NULL DEFAULT 'btc';
