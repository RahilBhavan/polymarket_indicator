# Architecture

Comprehensive overview of the CryptoSignal bot architecture, components, and data flow.

## Table of Contents

- [System Overview](#system-overview)
- [Architecture Diagram](#architecture-diagram)
- [Components](#components)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [Signal Generation Pipeline](#signal-generation-pipeline)
- [Technology Stack](#technology-stack)
- [Design Patterns](#design-patterns)
- [Security Model](#security-model)

---

## System Overview

CryptoSignal is a **signals-only Telegram bot** that generates daily Bitcoin trading recommendations for Polymarket prediction markets. It uses expected value (EV) analysis, Kelly criterion for position sizing, and multiple data sources to make informed predictions.

### Key Characteristics

- **Signals-only**: Provides recommendations, does not execute trades
- **EV-based**: Calculates edge between model probability and market probability
- **Risk-managed**: Uses fractional Kelly criterion for position sizing
- **Resilient**: Circuit breakers, retries, graceful degradation
- **Observable**: Structured logging, health monitoring, analytics
- **Extensible**: Modular fetcher system, pluggable data sources

---

## Architecture Diagram

```mermaid
graph TB
    subgraph "External Services"
        TG[Telegram API]
        PM[Polymarket API]
        FG[Fear & Greed API]
        BN[Binance API]
        DXY[Yahoo Finance]
        ETF[ETF Flows API]
        EX[Exchange Netflow API]
    end

    subgraph "CryptoSignal Bot"
        subgraph "API Layer"
            WH[Webhook Handler]
            CRON[Cron Endpoints]
            HEALTH[Health Check]
        end

        subgraph "Core Services"
            CMD[Command Handler]
            SIG[Signal Engine]
            OUT[Outcome Recorder]
            AN[Analytics]
        end

        subgraph "Data Layer"
            FETCH[Fetcher Registry]
            PM_CLIENT[Polymarket Client]
            DB[Database Session]
        end

        subgraph "Storage"
            PG[(PostgreSQL)]
        end
    end

    TG -->|Webhook| WH
    WH --> CMD
    CMD --> SIG
    CMD --> AN
    CMD --> DB

    CRON --> SIG
    CRON --> OUT

    SIG --> FETCH
    SIG --> PM_CLIENT
    SIG --> DB

    FETCH --> FG
    FETCH --> BN
    FETCH --> DXY
    FETCH --> ETF
    FETCH --> EX

    PM_CLIENT --> PM

    OUT --> PM
    OUT --> DB

    AN --> DB
    HEALTH --> DB

    DB --> PG

    CMD -->|Send Messages| TG

    style TG fill:#0088cc
    style PM fill:#0088cc
    style PG fill:#336791
    style SIG fill:#ff6b6b
    style FETCH fill:#4ecdc4
```

---

## Components

### 1. API Layer

**FastAPI Application** (`src/app/main.py`)
- **Health Endpoint**: `/health` - Database status, last signal time
- **Webhook Endpoint**: `/webhook/telegram` - Receives Telegram updates
- **Cron Endpoints**: `/internal/*` - Daily signal, EOD outcomes, heartbeat
- **API Endpoints**: `/api/signals`, `/api/stats` - Read-only data access

**Lifespan Management**:
- Initializes database connection pool on startup
- Validates production configuration
- Gracefully closes connections on shutdown

### 2. Telegram Integration

**Webhook Handler** (`src/app/telegram/webhook.py`)
- Validates `X-Telegram-Bot-Api-Secret-Token` header
- Returns 403 for invalid/missing secrets
- Routes updates to command handler

**Command Handler** (`src/app/telegram/handler.py`)
- Whitelists users (checks `TELEGRAM_ALLOWED_USER_IDS`)
- Dispatches commands: `/start`, `/signal`, `/stats`, `/history`, `/settings`, `/help`
- Rate limiting per user/command

**Commands** (`src/app/telegram/commands.py`):
- `/signal` - Generate today's signal
- `/stats` - Win rate, streak, drawdown, calibration
- `/history N` - Last N signals with outcomes
- `/settings` - Configure bankroll, verbosity, min confidence

**Message Formatting** (`src/app/telegram/formatter.py`):
- Emoji-rich signal displays
- Table formatting for stats
- Conditional verbosity (show/hide reasoning)

### 3. Data Fetchers

**Fetcher Registry** (`src/app/fetchers/registry.py`)
- Orchestrates parallel fetching from all sources
- Applies circuit breaker pattern
- Handles failures gracefully (partial data OK)

**Base Fetcher** (`src/app/fetchers/base.py`):
- Retry logic with exponential backoff
- Circuit breaker (open after N failures)
- Caching with TTL
- Structured error logging

**Implemented Fetchers**:
- `etf_flows.py` - Bitcoin ETF flow indicator
- `exchange_netflow.py` - Exchange net flow (requires paid API)
- `dxy.py` - Dollar Index 5-day trend
- `fear_greed.py` - Crypto Fear & Greed Index
- `funding.py` - Futures funding rates
- `price_ma.py` - Price vs moving averages
- `macro.py` - Macro factor aggregation
- `coinbase_premium.py` - Coinbase premium (optional)
- `stablecoin_issuance.py` - Stablecoin supply (optional)

### 4. Signal Engine

**Engine Orchestrator** (`src/app/signal/engine.py`):
1. Fetch all data sources in parallel
2. Compute weighted score from normalized features
3. Convert score to model probability
4. Get market probability from Polymarket
5. Calculate edge (Model_P - Market_P)
6. Apply edge threshold filter
7. Calculate Kelly-based position size
8. Build reasoning summary
9. Store in database

**Edge Calculator** (`src/app/signal/edge.py`):
- Computes directional edge
- Determines YES/NO/NO_TRADE
- Applies minimum edge threshold

**Kelly Sizer** (`src/app/signal/kelly.py`):
- Fractional Kelly formula
- Respects max bankroll % cap
- Handles edge cases (negative edge, extreme probabilities)

**Feature Weighting** (`src/app/signal/weights.py`):
- Configurable weights per source
- Normalized to sum to 1.0
- Override via environment variables

**Reasoning Builder** (`src/app/signal/reasoning.py`):
- Explains signal logic
- Shows which factors contributed most
- Flags stale/missing data

### 5. Polymarket Integration

**Gamma API Client** (`src/app/polymarket/client.py`):
- Public API for market data
- No auth required
- Rate limited

**CLOB API Client** (optional):
- Higher rate limits
- Requires API key
- Used for order book depth

**Market Selection** (`src/app/polymarket/selection.py`):
- Filters for BTC daily markets
- Checks market status (open, not resolved)
- Validates end times

**Order Book Analysis** (`src/app/polymarket/depth.py`):
- Calculates total liquidity
- Estimates slippage for given size
- Warns on thin markets

### 6. Outcome Recording

**EOD Recorder** (`src/app/outcomes/recorder.py`):
- Runs daily after market close (00:00+ UTC)
- Fetches market resolution from Polymarket
- Marks signals as WIN/LOSS/SKIP
- Stores actual outcome (YES/NO)
- Updates resolved_at timestamp

**Resolution Fetcher** (`src/app/outcomes/resolution.py`):
- Queries Polymarket for final outcome
- Handles edge cases (voided markets, delays)

### 7. Analytics

**Backtesting** (`src/app/analytics/backtest.py`):
- Replays historical signals
- Simulates P&L
- Calculates realized returns

**Calibration** (`src/app/analytics/calibration.py`):
- Groups predictions by confidence bucket
- Compares predicted vs actual win rates
- Detects over/under-confidence

**Rolling Metrics** (`src/app/analytics/rolling.py`):
- Win rate over last N signals
- Current streak (wins/losses)
- Time-weighted metrics

**Drawdown** (`src/app/analytics/drawdown.py`):
- Tracks peak-to-trough equity
- Calculates max drawdown
- Recovery analysis

**Factor Attribution** (`src/app/analytics/factor_attribution.py`):
- Which features correlated with wins
- Feature importance analysis

### 8. Database Layer

**Session Manager** (`src/app/db/session.py`):
- asyncpg connection pool
- Pool size: 1-5 connections
- Context manager for transactions
- Health check function

**Data Access Modules**:
- `signal_runs.py` - Signal CRUD operations
- `feature_snapshots.py` - Feature data storage
- `market_metadata.py` - Market condition tracking
- `user_prefs.py` - User settings

---

## Data Flow

### Signal Generation Flow

```mermaid
sequenceDiagram
    participant User
    participant Telegram
    participant Bot
    participant Fetchers
    participant Polymarket
    participant DB
    participant SignalEngine

    User->>Telegram: /signal
    Telegram->>Bot: Webhook
    Bot->>Bot: Validate user
    Bot->>SignalEngine: Generate signal

    par Fetch Data
        SignalEngine->>Fetchers: Fetch all sources
        Fetchers->>Fetchers: ETF Flows
        Fetchers->>Fetchers: Exchange Netflow
        Fetchers->>Fetchers: DXY
        Fetchers->>Fetchers: Fear & Greed
        Fetchers->>Fetchers: Price MA
        Fetchers->>Fetchers: Funding
        Fetchers->>Fetchers: Macro
    end

    SignalEngine->>SignalEngine: Compute weighted score
    SignalEngine->>Polymarket: Get market data
    Polymarket-->>SignalEngine: Market probability
    SignalEngine->>SignalEngine: Calculate edge
    SignalEngine->>SignalEngine: Calculate Kelly size

    SignalEngine->>DB: Store signal run
    SignalEngine->>DB: Store feature snapshots
    SignalEngine-->>Bot: Signal result

    Bot->>Telegram: Send message
    Telegram->>User: Signal display
```

### EOD Outcome Recording Flow

```mermaid
sequenceDiagram
    participant Cron
    participant Bot
    participant DB
    participant Polymarket

    Cron->>Bot: POST /internal/run-eod-outcomes
    Bot->>DB: Get unresolved signals

    loop For each signal
        DB-->>Bot: Signal details
        Bot->>Polymarket: Get market outcome
        Polymarket-->>Bot: Resolution (YES/NO)
        Bot->>Bot: Calculate WIN/LOSS
        Bot->>DB: Update outcome
    end

    Bot-->>Cron: Summary (updated, failed)
```

---

## Database Schema

```mermaid
erDiagram
    users ||--o{ user_prefs : has
    users {
        int id PK
        bigint telegram_user_id UK
        timestamptz created_at
    }

    user_prefs {
        int user_id PK,FK
        numeric bankroll_usd
        boolean is_verbose
        numeric min_confidence_pct
        timestamptz updated_at
    }

    signal_runs ||--o{ feature_snapshots : contains
    signal_runs {
        int id PK
        timestamptz run_at
        text asset
        text market_slug
        text market_condition_id
        text direction
        numeric model_p
        numeric market_p
        numeric edge
        numeric recommended_usd
        jsonb reasoning_json
        text liquidity_warning
        text status
        text outcome
        text actual_result
        timestamptz resolved_at
        jsonb order_book_snapshot
        timestamptz created_at
    }

    feature_snapshots {
        int id PK
        int signal_run_id FK
        text source_id
        text raw_value
        numeric normalized_score
        boolean stale
        timestamptz created_at
    }

    market_metadata {
        text condition_id PK
        text slug
        text resolution_source
        timestamptz end_date_utc
        timestamptz updated_at
    }

    schema_migrations {
        int id PK
        text version UK
        timestamptz applied_at
        text description
    }
```

**Key Tables:**

- **users**: Whitelisted Telegram users
- **user_prefs**: Per-user settings (bankroll, verbosity)
- **signal_runs**: One row per signal (direction, edge, outcome)
- **feature_snapshots**: Raw/normalized values from each fetcher
- **market_metadata**: Market info for outcome resolution
- **schema_migrations**: Applied migration tracking

**Indexes:**
- `signal_runs.run_at` - Fast time-based queries
- `signal_runs.outcome` - Filter by WIN/LOSS
- `feature_snapshots.signal_run_id` - Join with signals

---

## Signal Generation Pipeline

```mermaid
flowchart TD
    START[Start Signal Generation] --> FETCH[Fetch All Data Sources]

    FETCH --> CHECK{All Fetchers<br/>Succeeded?}
    CHECK -->|Partial Data| WARN[Log Warnings]
    CHECK -->|All Failed| ABORT[Abort: No Data]
    CHECK -->|Success| SCORE

    WARN --> SCORE[Compute Weighted Score]
    SCORE --> NORMALIZE[Normalize to 0-1]
    NORMALIZE --> PROB[Convert to Model Probability]

    PROB --> MARKET[Get Market Data from Polymarket]
    MARKET --> EDGE[Calculate Edge]

    EDGE --> THRESHOLD{Edge > Threshold?}
    THRESHOLD -->|No| NOTRADE[Direction: NO_TRADE]
    THRESHOLD -->|Yes| DIRECTION[Direction: YES/NO]

    DIRECTION --> KELLY[Calculate Kelly Size]
    KELLY --> CAP[Apply Max Bankroll Cap]

    CAP --> LIQUIDITY[Check Order Book Depth]
    LIQUIDITY --> SLIPPAGE{Slippage<br/>Acceptable?}
    SLIPPAGE -->|No| WARN2[Add Liquidity Warning]
    SLIPPAGE -->|Yes| REASON

    WARN2 --> REASON[Build Reasoning]
    NOTRADE --> REASON

    REASON --> STORE[Store to Database]
    STORE --> SEND[Send to Telegram]
    SEND --> END[End]

    ABORT --> END

    style START fill:#4ecdc4
    style END fill:#4ecdc4
    style ABORT fill:#ff6b6b
    style NOTRADE fill:#ffa500
    style DIRECTION fill:#95e1d3
```

---

## Technology Stack

### Backend
- **Python 3.11+** - Modern async syntax, type hints
- **FastAPI** - High-performance web framework
- **asyncpg** - Fast PostgreSQL driver
- **uvicorn** - ASGI server

### Database
- **PostgreSQL 15+** - Relational database for signals, outcomes
- **asyncpg pool** - Connection pooling for performance

### External APIs
- **Telegram Bot API** - Messaging platform
- **Polymarket Gamma API** - Market data (free)
- **Polymarket CLOB API** - Order book (optional)
- **Binance API** - Price and funding data
- **Yahoo Finance** - DXY (Dollar Index)
- **Alternative.me** - Fear & Greed Index

### Development
- **pytest** - Testing framework
- **respx** - HTTP mocking
- **ruff** - Fast linting and formatting
- **uv** - Fast package manager

### Deployment
- **Docker** - Containerization
- **docker-compose** - Local orchestration
- **GitHub Actions** - CI/CD

---

## Design Patterns

### 1. Circuit Breaker Pattern

**Purpose**: Prevent cascading failures from flaky external APIs

**Implementation**: `src/app/fetchers/base.py`

```python
class CircuitBreaker:
    - CLOSED: Normal operation, requests pass through
    - OPEN: After N failures, reject immediately
    - HALF_OPEN: After timeout, try one request
```

**Benefits**:
- Fast failure for known-bad endpoints
- Automatic recovery after cooldown
- Prevents resource exhaustion

### 2. Repository Pattern

**Purpose**: Separate data access from business logic

**Implementation**: `src/app/db/*.py`

```python
# Data access layer
await signal_runs.create(...)
await signal_runs.get_last_signal_at()

# Business logic doesn't know about SQL
```

**Benefits**:
- Easier testing (mock repositories)
- Centralized query logic
- Future ORM migration path

### 3. Strategy Pattern

**Purpose**: Pluggable fetcher implementations

**Implementation**: `src/app/fetchers/base.py`

```python
class BaseFetcher(ABC):
    @abstractmethod
    async def fetch(self) -> dict
```

**Benefits**:
- Easy to add new data sources
- Uniform error handling
- Independent testing

### 4. Command Pattern

**Purpose**: Telegram command dispatch

**Implementation**: `src/app/telegram/handler.py`

```python
HANDLERS = {
    "start": handle_start,
    "signal": handle_signal,
    "stats": handle_stats,
}
```

**Benefits**:
- Extensible command system
- Clear separation of concerns
- Easy to add/remove commands

---

## Security Model

### Authentication & Authorization

**Webhook Validation**:
- Telegram sends `X-Telegram-Bot-Api-Secret-Token`
- Bot verifies against `TELEGRAM_WEBHOOK_SECRET`
- Invalid requests rejected with 403

**User Whitelisting**:
- Only `TELEGRAM_ALLOWED_USER_IDS` can use bot
- Checked on every command
- Unauthorized users get friendly rejection

**Cron Job Protection**:
- Internal endpoints require `X-Cron-Secret` header
- Matches `EOD_CRON_SECRET` from environment
- Prevents unauthorized signal generation

### Data Protection

**Environment Variables**:
- Secrets in `.env` (never committed)
- Validated on startup
- Logged errors don't expose secrets

**Database Security**:
- No SQL injection (uses parameterized queries)
- Connection pool with timeout
- User-specific data isolated

**API Rate Limiting**:
- Telegram: Per-user command throttling
- External APIs: Respect rate limits with retries

### Attack Surface

**Exposed Endpoints**:
- `/webhook/telegram` - Telegram only, validated
- `/internal/*` - Secret-protected
- `/health` - Read-only, safe to expose

**Not Exposed**:
- Database credentials
- API keys
- Webhook secrets

---

## Scalability Considerations

### Current Architecture (Single Instance)

**Bottlenecks**:
- Database connection pool (max 5 connections)
- Single-threaded signal generation
- In-memory circuit breaker state

**Capacity**:
- ~100 users
- ~1000 signals/day
- Low latency (<2s for /signal)

### Future Scaling Options

**Horizontal Scaling**:
- Add load balancer
- Run multiple instances
- Use Redis for circuit breaker state
- Shared PostgreSQL instance

**Database Optimization**:
- Read replicas for analytics
- Partitioning for signal_runs (by month)
- Materialized views for stats

**Caching**:
- Redis for fetcher results
- CDN for static assets (if web UI added)

---

## Extension Points

### Adding New Data Sources

1. Create fetcher in `src/app/fetchers/`
2. Inherit from `BaseFetcher`
3. Implement `fetch()` method
4. Add to `FetcherRegistry`
5. Add weight to `weights.py`

### Adding New Commands

1. Add handler to `src/app/telegram/commands.py`
2. Register in `handler.py`
3. Update `/help` text
4. Add tests in `tests/unit/`

### Adding New Analytics

1. Create module in `src/app/analytics/`
2. Add database queries as needed
3. Expose via `/api/stats` or new endpoint
4. Add tests

---

**Next Steps:**
- [Development Guide](./DEVELOPMENT.md) - Contributing and customization
- [API Reference](./runbook.md) - Endpoint documentation
- [Testing Guide](../tests/README.md) - Test structure

---

**Questions?** See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) or open an issue.
