-- Add optional bet size (max USD) and Kelly fraction override to user_prefs.
-- When bet_size_usd is set, recommended bet is min(Kelly recommendation, bet_size_usd).
-- When kelly_fraction_override is set, it overrides config kelly_fraction for that user.

ALTER TABLE user_prefs
ADD COLUMN IF NOT EXISTS bet_size_usd NUMERIC(18, 2),
ADD COLUMN IF NOT EXISTS kelly_fraction_override NUMERIC(5, 4);

COMMENT ON COLUMN user_prefs.bet_size_usd IS 'Optional max bet in USD; Kelly recommendation is capped by this.';
COMMENT ON COLUMN user_prefs.kelly_fraction_override IS 'Optional Kelly fraction (e.g. 0.25); overrides app config for this user.';
