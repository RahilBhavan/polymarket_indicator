-- Phase 5: Add actual_result to signal_runs (YES/NO resolved outcome).
-- Run once on existing DBs: psql $DATABASE_URL -f scripts/migrate_add_actual_result.sql
ALTER TABLE signal_runs ADD COLUMN IF NOT EXISTS actual_result TEXT;
