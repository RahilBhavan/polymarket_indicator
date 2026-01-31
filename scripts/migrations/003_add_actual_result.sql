-- Phase 5: Add actual_result to signal_runs (YES/NO resolved outcome)
-- This column stores the actual market resolution for calibration and history analysis
-- New databases using 001_baseline.sql already have this column

ALTER TABLE signal_runs
ADD COLUMN IF NOT EXISTS actual_result TEXT;
