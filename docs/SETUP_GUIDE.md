# Setup Guide

Comprehensive guide to installing and configuring the CryptoSignal bot.

## Table of Contents

- [System Requirements](#system-requirements)
- [Installing Prerequisites](#installing-prerequisites)
- [One-Command Setup](#one-command-setup)
- [Manual Setup](#manual-setup)
- [Telegram Bot Creation](#telegram-bot-creation)
- [Database Configuration](#database-configuration)
- [Environment Variables](#environment-variables)
- [Webhook Setup](#webhook-setup)
- [Running the Bot](#running-the-bot)
- [Testing Your Setup](#testing-your-setup)

---

## System Requirements

### Minimum Requirements

- **Operating System**: macOS, Linux, or Windows (WSL recommended)
- **Python**: 3.11 or later
- **PostgreSQL**: 15 or later
- **Memory**: 512 MB RAM minimum (1 GB recommended)
- **Disk Space**: 500 MB for application and dependencies
- **Network**: Internet connection for API calls and Telegram

### Recommended for Production

- **Memory**: 2 GB RAM
- **CPU**: 2 cores
- **PostgreSQL**: Dedicated instance or managed service
- **HTTPS**: Reverse proxy (nginx, Caddy) or platform with SSL

---

## Installing Prerequisites

### Python 3.11+

#### macOS
```bash
# Using Homebrew
brew install python@3.11

# Verify installation
python3 --version  # Should show 3.11.x or higher
```

#### Ubuntu/Debian
```bash
# Add deadsnakes PPA for latest Python
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3.11-dev

# Set as default (optional)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Verify
python3 --version
```

#### Windows
1. Download from [python.org](https://www.python.org/downloads/)
2. Run installer
3. ✅ Check "Add Python to PATH"
4. Verify in PowerShell: `python --version`

---

### Installing PostgreSQL

#### macOS
```bash
# Using Homebrew
brew install postgresql@15

# Start PostgreSQL
brew services start postgresql@15

# Verify
psql --version
```

#### Ubuntu/Debian
```bash
# Add PostgreSQL repository
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -

# Install PostgreSQL 15
sudo apt update
sudo apt install postgresql-15 postgresql-contrib-15

# Start service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Verify
psql --version
```

#### Windows
1. Download installer from [postgresql.org](https://www.postgresql.org/download/windows/)
2. Run installer, follow wizard
3. Remember the password you set for postgres user
4. Verify installation

---

### uv Package Manager

The setup script installs this automatically, but you can also install manually:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH
export PATH="$HOME/.cargo/bin:$PATH"

# macOS (via Homebrew)
brew install uv

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## One-Command Setup

**Recommended for most users**

```bash
# Clone repository (if not already done)
git clone https://github.com/your-repo/cryptosignal.git
cd cryptosignal

# Run setup
./scripts/setup.sh
```

The setup script will:
1. ✅ Check Python 3.11+
2. ✅ Install `uv` if needed
3. ✅ Create `.env` with interactive prompts
4. ✅ Validate environment variables
5. ✅ Install all dependencies
6. ✅ Initialize PostgreSQL database
7. ✅ Show next steps

See [QUICK_START.md](./QUICK_START.md) for details.

---

## Manual Setup

If you prefer manual control or need to troubleshoot:

### 1. Clone Repository
```bash
git clone https://github.com/your-repo/cryptosignal.git
cd cryptosignal
```

### 2. Create Virtual Environment
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows

# Or using standard venv
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
# Using uv (fast)
uv sync --all-extras

# Or using pip
pip install -e ".[dev]"
```

### 4. Configure Environment
```bash
# Copy template
cp .env.example .env

# Edit with your values
nano .env  # or vim, code, etc.
```

See [Environment Variables](#environment-variables) below for what to set.

### 5. Create Database
```bash
# Connect to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE cryptosignal;
CREATE USER cryptosignal WITH PASSWORD 'changeme';
GRANT ALL PRIVILEGES ON DATABASE cryptosignal TO cryptosignal;
\q
```

### 6. Initialize Database Schema
```bash
# Automated (recommended)
uv run python scripts/init_db.py

# Or manual
psql "$DATABASE_URL" -f src/app/db/schema.sql
psql "$DATABASE_URL" -f scripts/migrations/002_add_asset.sql
psql "$DATABASE_URL" -f scripts/migrations/003_add_actual_result.sql
psql "$DATABASE_URL" -f scripts/migrations/004_add_order_book_snapshot.sql
```

### 7. Validate Setup
```bash
uv run python scripts/validate_env.py
```

---

## Telegram Bot Creation

### Step 1: Create Bot with BotFather

1. Open Telegram
2. Search for [@BotFather](https://t.me/botfather)
3. Send `/newbot`
4. Follow prompts:
   - Choose a name (e.g., "My CryptoSignal Bot")
   - Choose a username (e.g., "mycryptosignal_bot")
5. **Save the token** - looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

### Step 2: Configure Bot Settings

Send these commands to @BotFather:

```
/mybots
[Select your bot]
Edit Bot > Edit Description

Add a description:
"Polymarket BTC daily trading signals. Signals-only, no trading."

/mybots
[Select your bot]
Edit Bot > Edit Commands

Add commands:
start - Welcome message
signal - Get today's signal
stats - View win rate and performance
history - View recent signals
settings - Configure preferences
help - List all commands
status - Check bot health
```

### Step 3: Get Your User ID

1. Message [@userinfobot](https://t.me/userinfobot)
2. It will reply with your user ID (numeric)
3. **Save this ID** - you'll need it for `TELEGRAM_ALLOWED_USER_IDS`

### Step 4: Generate Webhook Secret

```bash
# Generate a secure random secret
openssl rand -hex 32
```

Save this for `TELEGRAM_WEBHOOK_SECRET` in your `.env`.

---

## Database Configuration

### Local Development

**Using default settings:**
```bash
DATABASE_URL=postgresql://cryptosignal:changeme@localhost:5432/cryptosignal
```

**Creating database and user:**
```sql
-- Connect as postgres superuser
psql -U postgres

-- Create user
CREATE ROLE cryptosignal WITH LOGIN PASSWORD 'changeme';

-- Create database
CREATE DATABASE cryptosignal OWNER cryptosignal;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE cryptosignal TO cryptosignal;

-- Verify
\l  -- List databases
\du -- List users
\q  -- Quit
```

### Remote PostgreSQL

For managed databases (AWS RDS, DigitalOcean, etc.):

```bash
# Format
DATABASE_URL=postgresql://username:password@host:port/database

# Example (AWS RDS)
DATABASE_URL=postgresql://dbuser:secure_password@mydb.abc123.us-east-1.rds.amazonaws.com:5432/cryptosignal

# Example (DigitalOcean)
DATABASE_URL=postgresql://doadmin:password@db-postgresql-nyc3-12345.ondigitalocean.com:25060/cryptosignal?sslmode=require
```

### Docker PostgreSQL

Using the included docker-compose.yml:

```bash
# Start PostgreSQL only
docker-compose up -d db

# Connect
psql postgresql://cryptosignal:changeme@localhost:5432/cryptosignal
```

---

## Environment Variables

### Required Variables

Copy these to your `.env` and fill in:

```bash
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_WEBHOOK_SECRET=abc123...  # 32+ characters
TELEGRAM_ALLOWED_USER_IDS=123456789  # Your Telegram user ID

# Database
DATABASE_URL=postgresql://cryptosignal:changeme@localhost:5432/cryptosignal
```

### Recommended for Production

```bash
# Admin alerts
ADMIN_CHAT_ID=123456789  # Your Telegram ID for error alerts

# Cron job protection
EOD_CRON_SECRET=xyz789...  # 32+ characters

# Environment
ENV=production
```

### Optional Tuning

**Signal Generation:**
```bash
# Higher = fewer but higher-confidence signals
EDGE_THRESHOLD=0.05  # 5% minimum edge

# Position sizing (0.25 = quarter Kelly)
KELLY_FRACTION=0.25

# Maximum position size (5% of bankroll)
MAX_BANKROLL_PCT=0.05

# Slippage tolerance
SLIPPAGE_LIMIT=0.01  # 1%

# Default bankroll
DEFAULT_BANKROLL_USD=1000
```

**Data Fetchers:**
```bash
# Timeouts and retries
FETCHER_TIMEOUT=15
RETRY_ATTEMPTS=3
CIRCUIT_FAILURE_THRESHOLD=3
CIRCUIT_OPEN_SECONDS=300
CACHE_TTL_SECONDS=3600
```

**Feature Weights:**
```bash
# Override default weights (0.0 to 1.0)
WEIGHT_ETF_FLOWS=0.20
WEIGHT_EXCHANGE_NETFLOW=0.20
WEIGHT_DXY=0.15
WEIGHT_FEAR_GREED=0.15
WEIGHT_PRICE_MA=0.15
WEIGHT_FUNDING=0.10
WEIGHT_MACRO=0.05
```

**Paper Trading:**
```bash
# Enable paper trading mode (no real money)
PAPER_TRADING=true
```

See [.env.example](../.env.example) for complete list with descriptions.

---

## Webhook Setup

Telegram requires HTTPS for webhooks. Choose based on your deployment:

### Option 1: Local Development with ngrok

**Install ngrok:**
```bash
# macOS
brew install ngrok

# Linux
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-*.tgz
sudo mv ngrok /usr/local/bin

# Windows
# Download from https://ngrok.com/download
```

**Use ngrok:**
```bash
# Start your bot
./scripts/dev.sh

# In another terminal
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
```

**Register webhook:**
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://abc123.ngrok.io/webhook/telegram" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>"
```

**Verify:**
```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

### Option 2: Production with Domain

If you have a domain with SSL certificate:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://yourdomain.com/webhook/telegram" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>"
```

### Option 3: Platform with Auto-SSL

Platforms like Fly.io, Railway, Render provide HTTPS automatically:

```bash
# After deploying, use the platform URL
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-app.fly.dev/webhook/telegram" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>"
```

---

## Running the Bot

### Development Mode

```bash
./scripts/dev.sh
```

Features:
- Auto-reload on code changes
- Detailed logging
- Runs on http://localhost:8000

### Production Mode

**Direct:**
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Docker Compose:**
```bash
docker-compose up -d
```

**Check status:**
```bash
# Health endpoint
curl http://localhost:8000/health

# Docker logs
docker-compose logs -f app
```

---

## Testing Your Setup

### 1. Validate Environment
```bash
uv run python scripts/validate_env.py --mode all
```

### 2. Check Database
```bash
# Migration status
uv run python scripts/migrate.py status

# Test connection
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM schema_migrations;"
```

### 3. Start Bot
```bash
./scripts/dev.sh
```

### 4. Check Health
```bash
curl http://localhost:8000/health | jq
```

Should return:
```json
{
  "status": "ok",
  "db": "connected",
  "last_signal_at": null,
  "data_sources": []
}
```

### 5. Test Telegram Commands

Message your bot on Telegram:
- `/start` - Should get welcome message
- `/status` - Should show database status
- `/help` - Should list commands

### 6. Test Signal Generation

```bash
# Manual signal (requires webhook setup)
curl -X POST "http://localhost:8000/internal/run-daily-signal" \
  -H "X-Cron-Secret: <YOUR_EOD_CRON_SECRET>"
```

### 7. Run Test Suite

```bash
./scripts/test.sh --coverage
```

---

## Next Steps

Once setup is complete:

1. **Configure cron jobs** for daily signals and EOD outcomes
2. **Set up monitoring** with health checks
3. **Review security** settings in production
4. **Read operations guide**: [runbook.md](./runbook.md)
5. **Customize features**: [DEVELOPMENT.md](./DEVELOPMENT.md)

---

## Common Setup Issues

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for solutions to:
- Python version errors
- PostgreSQL connection problems
- Telegram webhook issues
- Environment validation failures
- Migration errors

---

**Need help?** Check [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) or open an issue.

**Ready to develop?** See [DEVELOPMENT.md](./DEVELOPMENT.md) for contribution guide.
