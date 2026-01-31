# CryptoSignal Bot

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 15+](https://img.shields.io/badge/postgresql-15+-blue.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Polymarket BTC daily signal Telegram bot** - Generates trading signals using EV/edge logic, fractional Kelly sizing, and liquidity analysis. Signals-only mode (no actual trading).

---

## ⚡ Quick Start

Get running in 5 minutes:

```bash
./scripts/setup.sh
```

That's it! The setup script handles everything:
- ✅ Python 3.11+ check
- ✅ Dependency installation
- ✅ Configuration with interactive prompts
- ✅ Database initialization with migrations
- ✅ Environment validation

**Full guide:** [docs/QUICK_START.md](docs/QUICK_START.md)

---

## 📋 Prerequisites

Before setup, make sure you have:

- **Python 3.11+** ([Download](https://www.python.org/downloads/))
- **PostgreSQL 15+** ([Install Guide](docs/SETUP_GUIDE.md#installing-postgresql))
- **Telegram Bot Token** from [@BotFather](https://t.me/botfather)
- **Your Telegram User ID** from [@userinfobot](https://t.me/userinfobot)

---

## 🚀 Running the Bot

### Development Mode (with auto-reload)
```bash
./scripts/dev.sh
```

### Production Mode
```bash
docker-compose up -d
```

Or manually:
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Set Telegram webhook
After the app is reachable via HTTPS (e.g. ngrok or your domain), register the webhook so Telegram sends updates to your server:
```bash
./scripts/setup_webhook.sh <YOUR_HTTPS_BASE_URL>
```
Example: `./scripts/setup_webhook.sh https://abc123.ngrok-free.app`  
Check status: `uv run python scripts/check_webhook.py`

---

## 📖 Documentation

| Guide | Description |
|-------|-------------|
| [Quick Start](docs/QUICK_START.md) | Get running in 5 minutes |
| [Setup Guide](docs/SETUP_GUIDE.md) | Detailed configuration and installation |
| [Architecture](docs/ARCHITECTURE.md) | How the system works |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Solutions to common problems |
| [Development Guide](docs/DEVELOPMENT.md) | Contributing and customization |
| [Runbook](docs/runbook.md) | Operations and deployment |
| [Deploy Render + Neon](docs/DEPLOY_RENDER_NEON.md) | Free-tier deploy (Render + Neon) |

---

## 🧪 Testing

```bash
# Run all tests
./scripts/test.sh

# Run with coverage
./scripts/test.sh --coverage

# Run specific tests
./scripts/test.sh -k test_health
```

---

## 🛠️ Development

### Code Quality
```bash
# Lint
uv run ruff check src tests

# Format
uv run ruff format src tests

# Both (for CI)
uv run ruff check src tests && uv run ruff format --check src tests
```

### Database Management
```bash
# Check migration status
uv run python scripts/init_db.py --status

# Apply migrations
uv run python scripts/init_db.py

# Validate environment
uv run python scripts/validate_env.py
```

---

## 🏗️ Architecture

**Key Features:**
- 🤖 **Signals-only** - Recommendations, not trades
- 📊 **EV-based** - Expected value and edge calculation
- 💰 **Kelly sizing** - Position sizing with fractional Kelly criterion
- 🔄 **Async everything** - FastAPI + asyncpg for performance
- 🗄️ **PostgreSQL** - Source of truth for all signals and outcomes
- 🔒 **Secure** - Webhook validation, user whitelisting, secret management
- 📈 **Analytics** - Win rate, calibration, streaks, drawdowns
- 🚨 **Resilient** - Circuit breakers, retries, health monitoring

**9-Phase Architecture:**
1. Foundation (FastAPI, DB, config)
2. Polymarket integration
3. Data fetchers (7+ sources with circuit breakers)
4. Signal engine (scoring, Kelly, edge gating)
5. Outcome recording & analytics
6. Telegram UX
7. Google Sheets sync (optional)
8. Paper trading audit
9. Production deployment

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

---

## 🔧 Configuration

Core environment variables in `.env`:

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_SECRET=random_32_char_secret
TELEGRAM_ALLOWED_USER_IDS=123456789
DATABASE_URL=postgresql://user:pass@localhost:5432/cryptosignal

# Recommended
EOD_CRON_SECRET=random_secret_for_cron_jobs
ADMIN_CHAT_ID=your_telegram_id

# Optional (smart defaults)
PAPER_TRADING=false
EDGE_THRESHOLD=0.05
KELLY_FRACTION=0.25
```

See [.env.example](.env.example) for all options.

---

## 📊 Health Monitoring

```bash
# Health check
curl http://localhost:8000/health

# Returns 200 when healthy:
{
  "status": "ok",
  "db": "connected",
  "last_signal_at": "2026-01-30T12:00:00Z",
  "data_sources": [...]
}
```

---

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch:** `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Run tests:** `./scripts/test.sh`
5. **Commit:** `git commit -m 'Add amazing feature'`
6. **Push:** `git push origin feature/amazing-feature`
7. **Open a Pull Request**

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for coding guidelines.

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [asyncpg](https://github.com/MagicStack/asyncpg) - Fast PostgreSQL driver
- [Pydantic](https://pydantic.dev/) - Data validation
- [structlog](https://www.structlog.org/) - Structured logging

---

## 📬 Support

- **Documentation:** [docs/](docs/)
- **Issues:** [GitHub Issues](https://github.com/your-repo/issues)
- **Troubleshooting:** [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

**Ready to get started?** Run `./scripts/setup.sh` and you'll be trading signals in minutes! 🚀
