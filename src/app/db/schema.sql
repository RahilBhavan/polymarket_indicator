-- CryptoSignal bot: Postgres schema (source of truth)
--
-- RECOMMENDED: Use scripts/init_db.py to initialize database with migrations
--              This ensures proper migration tracking and idempotent setup
--
-- MANUAL: You can still run this file directly if you prefer:
--         psql "$DATABASE_URL" -f src/app/db/schema.sql
--         Then apply migrations manually from scripts/migrations/

-- Users: whitelisted Telegram users (optional; we can also rely on env list)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- User preferences (bankroll, verbosity, min confidence) for /settings
CREATE TABLE IF NOT EXISTS user_prefs (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bankroll_usd NUMERIC(18, 2) NOT NULL DEFAULT 1000,
    is_verbose BOOLEAN NOT NULL DEFAULT FALSE,
    min_confidence_pct NUMERIC(5, 2) NOT NULL DEFAULT 55,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id)
);

-- Signal runs: one row per daily signal generation
CREATE TABLE IF NOT EXISTS signal_runs (
    id SERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL,
    asset TEXT NOT NULL DEFAULT 'btc',  -- e.g. btc, eth for multi-asset
    market_slug TEXT,
    market_condition_id TEXT,
    direction TEXT NOT NULL,  -- YES | NO | NO_TRADE
    model_p NUMERIC(5, 4),
    market_p NUMERIC(5, 4),
    edge NUMERIC(5, 4),
    recommended_usd NUMERIC(18, 2),
    reasoning_json JSONB,
    liquidity_warning TEXT,
    status TEXT NOT NULL DEFAULT 'ok',  -- ok | partial | error
    outcome TEXT,   -- WIN | LOSS | SKIP (filled by EOD job)
    actual_result TEXT,  -- YES | NO (resolved market outcome; for calibration/history)
    resolved_at TIMESTAMPTZ,
    order_book_snapshot JSONB,  -- Paper mode: top levels + timestamp for slippage audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Feature snapshots: raw and normalized values per run per source (Phase 3+)
CREATE TABLE IF NOT EXISTS feature_snapshots (
    id SERIAL PRIMARY KEY,
    signal_run_id INTEGER NOT NULL REFERENCES signal_runs(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    raw_value TEXT,
    normalized_score NUMERIC(10, 4),
    stale BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Market metadata: condition_id, slug, resolution_source, end_date_utc (for outcome recording)
CREATE TABLE IF NOT EXISTS market_metadata (
    condition_id TEXT NOT NULL PRIMARY KEY,
    slug TEXT,
    resolution_source TEXT,
    end_date_utc TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signal_runs_run_at ON signal_runs(run_at);
CREATE INDEX IF NOT EXISTS idx_signal_runs_outcome ON signal_runs(outcome) WHERE outcome IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_feature_snapshots_run ON feature_snapshots(signal_run_id);
