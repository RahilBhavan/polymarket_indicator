"""Configuration from environment. All secrets via env; never in code."""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Load from env; validate on access."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment (optional; e.g. "production" for startup warnings)
    env: str = Field(default="development", description="ENV name for startup checks")

    # Telegram
    telegram_bot_token: str = Field(..., description="Bot token from BotFather")
    telegram_webhook_secret: str = Field(..., description="Secret token for webhook verification")
    telegram_allowed_user_ids: str = Field(
        ...,
        description="Comma-separated Telegram user IDs allowed to use the bot",
    )
    admin_chat_id: str | None = Field(
        default=None,
        description="Telegram chat ID for admin alerts (errors)",
    )

    # Database
    database_url: str = Field(..., description="Postgres connection URL (async)")

    # Data fetchers (Phase 3): timeouts, retries, circuit breaker, cache
    fetcher_timeout: float = Field(
        default=15.0, gt=0, le=120, description="HTTP timeout for fetcher requests (seconds)"
    )
    circuit_failure_threshold: int = Field(
        default=3, ge=1, le=20, description="Consecutive failures before opening circuit"
    )
    circuit_open_seconds: float = Field(
        default=300.0, gt=0, le=3600, description="Seconds to keep circuit open"
    )
    cache_ttl_seconds: float = Field(
        default=3600.0, gt=0, le=86400, description="Cache TTL for fetcher responses (seconds)"
    )
    retry_attempts: int = Field(
        default=3, ge=1, le=10, description="Fetcher retry attempts with exponential backoff"
    )
    retry_base_delay: float = Field(
        default=1.0, gt=0, le=30, description="Base delay in seconds for first retry"
    )

    # Optional: signal defaults (Phase 4+)
    edge_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    kelly_fraction: float = Field(default=0.25, ge=0.0, le=1.0)
    max_bankroll_pct: float = Field(default=0.05, ge=0.0, le=1.0)
    slippage_limit: float = Field(default=0.01, ge=0.0, le=0.1)
    default_bankroll_usd: float = Field(default=1000.0, gt=0)
    paper_trading: bool = Field(
        default=False, description="When True, tag signals as PAPER (no real money)"
    )

    # Phase 5: EOD outcomes job (cron calls after 00:00 UTC)
    eod_cron_secret: str | None = Field(
        default=None,
        description="Optional secret for POST /internal/run-eod-outcomes (X-Cron-Secret header)",
    )

    # Optional: factor weights (override defaults when set; env e.g. WEIGHT_ETF_FLOWS=0.25)
    weight_etf_flows: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_exchange_netflow: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_dxy: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_fear_greed: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_price_ma: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_funding: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_macro: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_coinbase_premium: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_stablecoin_issuance: float | None = Field(default=None, ge=0.0, le=1.0)

    # Optional fetchers (when true, include in registry and use weight above or default 0.05)
    fetch_coinbase_premium: bool = Field(
        default=False, description="Include Coinbase premium fetcher"
    )
    fetch_stablecoin_issuance: bool = Field(
        default=False, description="Include stablecoin issuance fetcher"
    )

    # BTC 15m Up/Down market selection (Gamma events by series_id)
    polymarket_series_id_15m: str = Field(
        default="10192", description="Gamma series_id for BTC 15m Up/Down events"
    )
    polymarket_up_label: str = Field(default="Up", description="Outcome label for Up")
    polymarket_down_label: str = Field(default="Down", description="Outcome label for Down")

    # Live BTC/USD price feed (Polymarket WS, Chainlink Polygon)
    polymarket_live_ws_url: str = Field(
        default="wss://ws-live-data.polymarket.com",
        description="Polymarket live data WebSocket URL",
    )
    polygon_rpc_url: str = Field(
        default="https://polygon-rpc.com",
        description="Polygon HTTP RPC URL for Chainlink fallback",
    )
    polygon_rpc_urls: str = Field(
        default="",
        description="Comma-separated Polygon RPC URLs (optional, overrides single URL)",
    )
    polygon_wss_url: str = Field(default="", description="Polygon WSS RPC URL (optional)")
    polygon_wss_urls: str = Field(
        default="",
        description="Comma-separated Polygon WSS URLs for Chainlink log subscription",
    )
    chainlink_btc_usd_aggregator: str = Field(
        default="0xc907E116054Ad103354f2D350FD2514433D57F6f",
        description="Chainlink BTC/USD aggregator contract on Polygon",
    )
    chainlink_http_cache_seconds: float = Field(
        default=2.0, gt=0, le=60, description="Min interval between Chainlink HTTP fetches (seconds)"
    )

    @model_validator(mode="after")
    def validate_allowed_user_ids(self) -> "Settings":
        """Fail fast if TELEGRAM_ALLOWED_USER_IDS contains invalid values (e.g. non-integer)."""
        try:
            ids = [int(x.strip()) for x in self.telegram_allowed_user_ids.split(",") if x.strip()]
            if not ids:
                raise ValueError("At least one user ID required")
        except ValueError as e:
            raise ValueError(
                f"TELEGRAM_ALLOWED_USER_IDS must be comma-separated positive integers: {e}"
            ) from e
        return self

    def allowed_user_ids_list(self) -> list[int]:
        """Parse comma-separated user IDs to list of ints."""
        return [int(x.strip()) for x in self.telegram_allowed_user_ids.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
