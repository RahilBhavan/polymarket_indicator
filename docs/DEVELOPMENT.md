# Development Guide

Guide for developers contributing to or customizing the CryptoSignal bot.

## Table of Contents

- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Adding Features](#adding-features)
- [Database Migrations](#database-migrations)
- [Debugging](#debugging)
- [Contributing](#contributing)

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Git
- Code editor (VS Code recommended)

### Initial Setup

```bash
# Clone repository
git clone https://github.com/your-repo/cryptosignal.git
cd cryptosignal

# Run setup
./scripts/setup.sh

# Create development branch
git checkout -b feature/your-feature-name
```

### Development Environment

```bash
# Start development server (auto-reload)
./scripts/dev.sh

# In another terminal, start ngrok for webhook testing
ngrok http 8000
```

### Recommended Tools

**VS Code Extensions:**
- Python
- Pylance
- Ruff
- PostgreSQL
- GitLens

**Command Line Tools:**
- `uv` - Fast package manager
- `psql` - PostgreSQL client
- `jq` - JSON processor
- `curl` - HTTP testing
- `ngrok` - HTTPS tunnel for local dev

---

## Project Structure

```
cryptosignal/
├── src/app/                    # Application code
│   ├── main.py                 # FastAPI app, lifespan, endpoints
│   ├── config.py               # Pydantic settings
│   ├── logging_config.py       # Structured logging
│   │
│   ├── db/                     # Database layer
│   │   ├── schema.sql          # Database schema
│   │   ├── session.py          # Connection pool, health check
│   │   ├── signal_runs.py      # Signal CRUD
│   │   ├── feature_snapshots.py # Feature data
│   │   ├── market_metadata.py  # Market info
│   │   └── user_prefs.py       # User settings
│   │
│   ├── telegram/               # Telegram integration
│   │   ├── handler.py          # Command dispatch
│   │   ├── webhook.py          # Webhook validation
│   │   ├── commands.py         # Command implementations
│   │   ├── formatter.py        # Message formatting
│   │   ├── send.py             # Send messages
│   │   ├── admin.py            # Admin alerts
│   │   └── rate_limit.py       # Rate limiting
│   │
│   ├── polymarket/             # Polymarket API
│   │   ├── client.py           # Gamma & CLOB clients
│   │   ├── models.py           # Data models
│   │   ├── selection.py        # Market filtering
│   │   └── depth.py            # Liquidity analysis
│   │
│   ├── fetchers/               # Data source fetchers
│   │   ├── base.py             # Base fetcher (circuit breaker)
│   │   ├── registry.py         # Fetcher orchestration
│   │   ├── etf_flows.py        # ETF flows
│   │   ├── exchange_netflow.py # Exchange netflow
│   │   ├── dxy.py              # Dollar Index
│   │   ├── fear_greed.py       # Fear & Greed
│   │   ├── funding.py          # Funding rates
│   │   ├── price_ma.py         # Price moving averages
│   │   └── macro.py            # Macro factors
│   │
│   ├── signal/                 # Signal generation
│   │   ├── engine.py           # Orchestrator
│   │   ├── edge.py             # Edge calculation
│   │   ├── kelly.py            # Kelly sizing
│   │   ├── weights.py          # Feature weights
│   │   ├── score_to_prob.py    # Score conversion
│   │   └── reasoning.py        # Reasoning builder
│   │
│   ├── outcomes/               # Outcome recording
│   │   ├── recorder.py         # EOD job
│   │   └── resolution.py       # Market resolution
│   │
│   └── analytics/              # Analytics & backtesting
│       ├── backtest.py         # Historical replay
│       ├── calibration.py      # Probability calibration
│       ├── rolling.py          # Rolling metrics
│       ├── drawdown.py         # Drawdown analysis
│       └── factor_attribution.py # Feature importance
│
├── tests/                      # Test suite
│   ├── conftest.py             # Pytest fixtures
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── fuzz/                   # Fuzz tests
│
├── scripts/                    # Utility scripts
│   ├── setup.sh                # One-command setup
│   ├── dev.sh                  # Development server
│   ├── test.sh                 # Test runner
│   ├── init_db.py              # Database initialization
│   ├── validate_env.py         # Environment validation
│   ├── migrate.py              # Migration management
│   └── migrations/             # Database migrations
│
├── docs/                       # Documentation
│   ├── QUICK_START.md          # Getting started
│   ├── SETUP_GUIDE.md          # Detailed setup
│   ├── ARCHITECTURE.md         # System design
│   ├── TROUBLESHOOTING.md      # Common issues
│   ├── DEVELOPMENT.md          # This file
│   └── runbook.md              # Operations guide
│
├── docker/                     # Docker files
│   └── Dockerfile              # Production image
│
├── .env.example                # Environment template
├── .gitignore                  # Git ignore rules
├── docker-compose.yml          # Local stack
├── pyproject.toml              # Project metadata, dependencies
└── README.md                   # Project overview
```

---

## Development Workflow

### 1. Start Development Server

```bash
./scripts/dev.sh
```

This starts uvicorn with:
- Auto-reload on file changes
- Host: 0.0.0.0 (accessible from network)
- Port: 8000

### 2. Make Changes

Edit code in `src/app/`. The server will auto-reload.

### 3. Run Tests

```bash
# All tests
./scripts/test.sh

# With coverage
./scripts/test.sh --coverage

# Specific test
./scripts/test.sh -k test_health
```

### 4. Check Code Quality

```bash
# Lint
uv run ruff check src tests

# Format
uv run ruff format src tests

# Type check (if mypy installed)
uv run mypy src
```

### 5. Commit Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "feat: add new data fetcher for X"

# Follow conventional commits format:
# feat: new feature
# fix: bug fix
# docs: documentation
# test: testing
# refactor: code refactoring
# chore: maintenance
```

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub.

---

## Code Style

### General Principles

1. **Type hints** on all functions
2. **Docstrings** for public APIs
3. **Async by default** for I/O operations
4. **Fail fast** with clear error messages
5. **Structured logging** instead of print()

### Python Style

We use **Ruff** for linting and formatting:

```bash
# Auto-format
uv run ruff format src tests

# Fix auto-fixable issues
uv run ruff check --fix src tests
```

**Key conventions:**
- Line length: 100 characters
- Import order: stdlib, third-party, local
- String quotes: Double quotes
- Trailing commas: Yes (for multi-line)

### Example Code

```python
"""Module for X functionality."""

import asyncio
from typing import Optional

from pydantic import BaseModel

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class MyModel(BaseModel):
    """Data model for X."""

    field1: str
    field2: Optional[int] = None


async def my_function(param: str, *, timeout: int = 30) -> dict[str, any]:
    """
    Do something useful.

    Args:
        param: Description of param
        timeout: Operation timeout in seconds

    Returns:
        Dictionary with results

    Raises:
        ValueError: If param is invalid
    """
    if not param:
        raise ValueError("param is required")

    logger.info("doing_something", param=param, timeout=timeout)

    # Implementation here
    result = {"status": "ok"}

    return result
```

---

## Testing

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Fast, isolated tests
│   ├── test_config.py       # Config validation
│   ├── test_signal_engine.py
│   └── test_*.py
├── integration/             # Tests with external deps
│   ├── test_polymarket_api.py
│   └── test_database.py
└── fuzz/                    # Property-based tests
    └── test_kelly_fuzz.py
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_config.py

# Specific test function
pytest tests/unit/test_config.py::test_required_vars

# With coverage
pytest --cov=src/app --cov-report=html

# Verbose output
pytest -v

# Show print statements
pytest -s
```

### Writing Tests

**Unit Test Example:**

```python
"""Tests for signal engine."""

import pytest

from app.signal.edge import calculate_edge


def test_calculate_edge_yes_signal():
    """Test edge calculation for YES signal."""
    model_p = 0.60
    market_p = 0.50

    direction, edge = calculate_edge(model_p, market_p, edge_threshold=0.05)

    assert direction == "YES"
    assert edge == 0.10


def test_calculate_edge_no_trade():
    """Test NO_TRADE when edge below threshold."""
    model_p = 0.52
    market_p = 0.50

    direction, edge = calculate_edge(model_p, market_p, edge_threshold=0.05)

    assert direction == "NO_TRADE"
    assert edge == 0.02
```

**Async Test Example:**

```python
import pytest

from app.db.session import init_pool, close_pool, health_check


@pytest.mark.asyncio
async def test_database_health():
    """Test database health check."""
    await init_pool()

    is_healthy = await health_check()

    assert is_healthy is True

    await close_pool()
```

**Mocking External APIs:**

```python
import respx
import httpx

from app.fetchers.fear_greed import FearGreedFetcher


@pytest.mark.asyncio
@respx.mock
async def test_fear_greed_fetcher():
    """Test Fear & Greed Index fetcher."""
    # Mock API response
    respx.get("https://api.alternative.me/fng/").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"value": "75", "value_classification": "Greed"}]},
        )
    )

    fetcher = FearGreedFetcher()
    result = await fetcher.fetch()

    assert result["normalized_score"] > 0
    assert result["raw_value"] == "75"
```

### Test Coverage

Aim for **80%+ coverage** of critical paths:
- Signal generation logic
- Database operations
- Telegram commands
- Edge/Kelly calculations

Less critical:
- Logging code
- Admin utilities
- Formatting helpers

---

## Adding Features

### Adding a New Data Fetcher

**1. Create fetcher file:**

```python
# src/app/fetchers/my_source.py
"""Fetcher for My Data Source."""

from app.fetchers.base import BaseFetcher


class MySourceFetcher(BaseFetcher):
    """Fetch data from My Source."""

    def __init__(self):
        super().__init__(
            source_id="my_source",
            cache_ttl=3600,
        )

    async def _fetch_impl(self) -> dict:
        """Fetch implementation."""
        async with self.client.get("https://api.example.com/data") as resp:
            data = await resp.json()

        # Normalize to 0-1 scale
        raw_value = data["value"]
        normalized_score = self._normalize(raw_value, min_val=0, max_val=100)

        return {
            "raw_value": str(raw_value),
            "normalized_score": normalized_score,
            "stale": False,
        }
```

**2. Register in registry:**

```python
# src/app/fetchers/registry.py
from app.fetchers.my_source import MySourceFetcher

async def fetch_all() -> dict[str, dict]:
    fetchers = [
        # ... existing fetchers
        MySourceFetcher(),
    ]
    # ...
```

**3. Add weight:**

```python
# src/app/signal/weights.py
DEFAULT_WEIGHTS = {
    # ... existing weights
    "my_source": 0.10,
}
```

**4. Add environment variable:**

```bash
# .env.example
# Optional: override weight
# WEIGHT_MY_SOURCE=0.10
```

**5. Add tests:**

```python
# tests/unit/test_my_source.py
import pytest
import respx

from app.fetchers.my_source import MySourceFetcher


@pytest.mark.asyncio
@respx.mock
async def test_my_source_fetcher():
    respx.get("https://api.example.com/data").mock(
        return_value=httpx.Response(200, json={"value": 75})
    )

    fetcher = MySourceFetcher()
    result = await fetcher.fetch()

    assert result["normalized_score"] == 0.75
```

### Adding a New Telegram Command

**1. Add handler:**

```python
# src/app/telegram/commands.py
async def handle_my_command(update: dict) -> str:
    """Handle /my_command."""
    # Extract user info
    user_id = update["message"]["from"]["id"]

    # Your logic here
    result = do_something()

    # Return message to send
    return f"Result: {result}"
```

**2. Register command:**

```python
# src/app/telegram/handler.py
COMMAND_HANDLERS = {
    # ... existing handlers
    "my_command": handle_my_command,
}
```

**3. Update help text:**

```python
# src/app/telegram/commands.py
async def handle_help(update: dict) -> str:
    return """
    ...
    /my_command - Do something useful
    ...
    """
```

**4. Add tests:**

```python
# tests/unit/test_commands.py
@pytest.mark.asyncio
async def test_my_command():
    update = {
        "message": {
            "from": {"id": 12345},
            "text": "/my_command",
        }
    }

    response = await handle_my_command(update)

    assert "Result:" in response
```

---

## Database Migrations

### Creating a Migration

```bash
# Create new migration file
cd scripts/migrations
touch 005_add_new_column.sql
```

**Migration template:**

```sql
-- Phase X: Add Y feature
-- This migration adds Z to support ABC

ALTER TABLE signal_runs
ADD COLUMN IF NOT EXISTS new_column TEXT;

-- Add index if needed
CREATE INDEX IF NOT EXISTS idx_signal_runs_new_column
ON signal_runs(new_column);
```

### Testing Migration

```bash
# Check status
uv run python scripts/migrate.py status

# Dry run
uv run python scripts/migrate.py apply --dry-run

# Apply
uv run python scripts/migrate.py apply

# Verify
psql "$DATABASE_URL" -c "\d signal_runs"
```

### Migration Best Practices

1. **One change per migration** - Easier to rollback
2. **Use IF NOT EXISTS** - Idempotent operations
3. **Test on copy of production data** - Catch edge cases
4. **No data loss** - Use ALTER ADD COLUMN, not DROP
5. **Document purpose** - Clear comments at top

---

## Debugging

### Enable Debug Logging

```python
# src/app/logging_config.py
configure_logging(debug=True)  # Change False to True
```

Restart bot to see detailed logs.

### Interactive Debugging

**Using pdb:**

```python
import pdb; pdb.set_trace()
```

**Using VS Code:**

1. Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        "8000"
      ],
      "jinja": true,
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src"
      }
    }
  ]
}
```

2. Set breakpoints
3. Press F5 to debug

### Common Debug Scenarios

**Database query not working:**

```python
# Log the SQL
logger.debug("query", sql=query, params=params)
```

**Fetcher returning unexpected data:**

```python
# Log raw response
logger.debug("fetcher_response", source=self.source_id, data=data)
```

**Signal calculation wrong:**

```python
# Log intermediate steps
logger.debug("signal_calc", model_p=model_p, market_p=market_p, edge=edge)
```

---

## Contributing

### Contribution Process

1. **Open an issue** to discuss the feature/fix
2. **Fork the repository**
3. **Create a feature branch**
4. **Make changes** with tests
5. **Run quality checks** (lint, format, tests)
6. **Submit Pull Request**
7. **Address review feedback**

### PR Checklist

Before submitting:

- [ ] Tests pass: `./scripts/test.sh`
- [ ] Linting passes: `uv run ruff check src tests`
- [ ] Code formatted: `uv run ruff format src tests`
- [ ] Documentation updated (if needed)
- [ ] Migration added (if schema changed)
- [ ] Environment variables documented (if new config)
- [ ] Commit messages follow conventional format

### Code Review Guidelines

**For Reviewers:**
- Check for security issues (SQL injection, secrets exposure)
- Verify tests cover new code
- Ensure error handling is appropriate
- Look for performance implications
- Suggest improvements kindly

**For Authors:**
- Respond to feedback promptly
- Explain your reasoning when disagreeing
- Keep PRs focused and small
- Update PR description if scope changes

---

## Advanced Topics

### Custom Pydantic Validators

```python
from pydantic import BaseModel, field_validator


class SignalConfig(BaseModel):
    edge_threshold: float

    @field_validator("edge_threshold")
    @classmethod
    def validate_threshold(cls, v):
        if not 0 < v < 1:
            raise ValueError("edge_threshold must be between 0 and 1")
        return v
```

### Custom Context Managers

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def temp_pool(url: str):
    pool = await asyncpg.create_pool(url)
    try:
        yield pool
    finally:
        await pool.close()
```

### Dependency Injection

```python
from fastapi import Depends


async def get_db_session():
    async with acquire() as conn:
        yield conn


@app.get("/api/signals")
async def api_signals(conn = Depends(get_db_session)):
    rows = await conn.fetch("SELECT ...")
```

---

## Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **asyncpg Docs**: https://magicstack.github.io/asyncpg/
- **Pydantic Docs**: https://docs.pydantic.dev/
- **Pytest Docs**: https://docs.pytest.org/
- **Ruff Docs**: https://docs.astral.sh/ruff/

---

**Questions?** Open an issue or check [TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

**Ready to contribute?** Read [ARCHITECTURE.md](./ARCHITECTURE.md) first!
