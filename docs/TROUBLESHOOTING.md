# Troubleshooting Guide

Common problems and their solutions for the CryptoSignal bot.

## Table of Contents

- [Setup Issues](#setup-issues)
- [Database Problems](#database-problems)
- [Telegram Webhook Issues](#telegram-webhook-issues)
- [Environment Configuration](#environment-configuration)
- [Data Fetcher Errors](#data-fetcher-errors)
- [Runtime Errors](#runtime-errors)
- [Migration Problems](#migration-problems)

---

## Setup Issues

### Python Version Too Old

**Symptom:**
```
❌ Python 3.11+ required (found 3.9.x)
```

**Solution:**

**macOS:**
```bash
brew install python@3.11
# Update PATH if needed:
export PATH="/usr/local/opt/python@3.11/bin:$PATH"
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv
# Set as default (optional):
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/) and install 3.11+

---

### uv Installation Failed

**Symptom:**
```
Failed to install uv
```

**Solution:**

Try manual installation:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or use alternative package managers:
```bash
# macOS
brew install uv

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Add to PATH:
```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

---

### Setup Script Fails on Permissions

**Symptom:**
```
Permission denied: ./scripts/setup.sh
```

**Solution:**
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

---

## Database Problems

### Connection Refused

**Symptom:**
```
Failed to connect to database: Connection refused
```

**Causes:**
1. PostgreSQL server not running
2. Wrong hostname/port
3. Firewall blocking connection

**Solutions:**

**Check if PostgreSQL is running:**
```bash
# macOS
brew services list | grep postgresql

# Linux
sudo systemctl status postgresql

# Check if listening on port 5432
sudo lsof -i :5432
```

**Start PostgreSQL:**
```bash
# macOS
brew services start postgresql@15

# Linux
sudo systemctl start postgresql
sudo systemctl enable postgresql  # auto-start on boot
```

**Verify connection manually:**
```bash
psql -h localhost -U cryptosignal -d postgres
# Enter password when prompted
```

---

### Database Does Not Exist

**Symptom:**
```
database "cryptosignal" does not exist
```

**Solution:**

Create the database manually:
```bash
# Connect to postgres database
psql -U postgres

# Create database
CREATE DATABASE cryptosignal;

# Create user (if needed)
CREATE USER cryptosignal WITH PASSWORD 'changeme';
GRANT ALL PRIVILEGES ON DATABASE cryptosignal TO cryptosignal;

# Exit
\q
```

Then run setup again:
```bash
./scripts/setup.sh
```

---

### Authentication Failed

**Symptom:**
```
password authentication failed for user "cryptosignal"
```

**Solution:**

1. **Check DATABASE_URL in .env:**
   ```
   postgresql://username:password@localhost:5432/cryptosignal
   ```

2. **Reset password:**
   ```bash
   psql -U postgres
   ALTER USER cryptosignal WITH PASSWORD 'newpassword';
   \q
   ```

3. **Update .env with new password**

4. **Check pg_hba.conf** (advanced):
   ```bash
   # Find config location
   psql -U postgres -c "SHOW hba_file"

   # Edit file and change 'peer' to 'md5' for local connections
   sudo nano /path/to/pg_hba.conf

   # Restart PostgreSQL
   sudo systemctl restart postgresql
   ```

---

### Migration Already Applied Error

**Symptom:**
```
ERROR: duplicate key value violates unique constraint "schema_migrations_version_key"
```

**Solution:**

This is harmless - the migration was already applied. To check status:
```bash
uv run python scripts/init_db.py --status
```

To force re-initialization (⚠️ **DESTRUCTIVE** - only for fresh DBs):
```bash
# Drop and recreate database
psql -U postgres -c "DROP DATABASE cryptosignal;"
psql -U postgres -c "CREATE DATABASE cryptosignal;"

# Re-run setup
./scripts/setup.sh
```

---

## Telegram Webhook Issues

### Webhook Not Receiving Messages

**Symptom:**
Bot doesn't respond to messages, no errors in logs.

**Diagnosis:**

Check webhook status:
```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo"
```

Look for:
- `url`: Should match your domain
- `has_custom_certificate`: Should be false
- `pending_update_count`: Should be 0
- `last_error_message`: Check for errors

**Common Issues:**

**1. URL not HTTPS**
Telegram requires HTTPS. For local dev, use ngrok:
```bash
ngrok http 8000
# Copy https URL, not http
```

**2. Webhook not set**
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/webhook/telegram" \
  -d "secret_token=<WEBHOOK_SECRET>"
```

**3. Wrong secret token**
Verify `secret_token` in webhook matches `TELEGRAM_WEBHOOK_SECRET` in .env

**4. Old pending updates**
Clear them:
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/deleteWebhook" \
  -d "drop_pending_updates=true"

# Then set webhook again
```

---

### 403 Forbidden on Webhook Endpoint

**Symptom:**
Telegram returns 403, logs show:
```
Unauthorized webhook: invalid secret
```

**Solution:**

1. **Check webhook secret matches:**
   ```bash
   # In .env:
   TELEGRAM_WEBHOOK_SECRET=your_secret_here

   # When setting webhook:
   secret_token=your_secret_here  # Must match exactly
   ```

2. **Re-register webhook** with correct secret

---

### Bot Responds Slowly

**Symptom:**
Messages take 5-10 seconds to get a response.

**Possible Causes:**

**1. Data fetchers timing out**
Check logs for:
```
fetcher_retry: attempt=3, error=timeout
circuit_open: source=exchange_netflow
```

**Solution:** Increase timeouts in .env:
```bash
FETCHER_TIMEOUT=30
RETRY_ATTEMPTS=5
```

**2. Database connection pool exhausted**
**Solution:** Restart the bot or increase pool size in `src/app/db/session.py`

**3. Circuit breaker open**
Some data sources may be failing. Check logs and wait for circuit to auto-close (5 minutes default).

---

## Environment Configuration

### Required Variable Not Set

**Symptom:**
```
❌ TELEGRAM_BOT_TOKEN is required but not set
```

**Solution:**

1. **Check .env exists:**
   ```bash
   ls -la .env
   ```

2. **Validate .env:**
   ```bash
   uv run python scripts/validate_env.py
   ```

3. **Copy from example:**
   ```bash
   cp .env.example .env
   nano .env  # Edit and fill in values
   ```

4. **Required variables and where to get them:**

   | Variable | Where to get it |
   |----------|-----------------|
   | `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/botfather) → `/newbot` → copy token (e.g. `123456:ABCdef...`) |
   | `TELEGRAM_WEBHOOK_SECRET` | Generate: `openssl rand -hex 32` (min 32 chars) |
   | `TELEGRAM_ALLOWED_USER_IDS` | [@userinfobot](https://t.me/userinfobot) → message it → copy your numeric ID; comma-separated for multiple |
   | `DATABASE_URL` | Local: `postgresql://cryptosignal:changeme@localhost:5432/cryptosignal` (create DB/user first; see [SETUP_GUIDE](SETUP_GUIDE.md#database-configuration)) |

   Ensure each line in `.env` is `KEY=value` with no spaces around `=`, and no quotes unless the value contains spaces. Re-run `./scripts/setup.sh` or `uv run python scripts/validate_env.py` after editing.

---

### Invalid DATABASE_URL Format

**Symptom:**
```
❌ DATABASE_URL: Must start with 'postgresql://'
```

**Correct Format:**
```
postgresql://username:password@hostname:port/database
```

**Examples:**
```bash
# Local development
DATABASE_URL=postgresql://cryptosignal:changeme@localhost:5432/cryptosignal

# Remote server
DATABASE_URL=postgresql://user:pass@db.example.com:5432/cryptosignal

# With special characters in password (URL encode them)
DATABASE_URL=postgresql://user:p%40ssw0rd@localhost:5432/cryptosignal
#                                  ^ @ is %40
```

---

### User ID Not Numeric

**Symptom:**
```
❌ TELEGRAM_ALLOWED_USER_IDS: Invalid user ID 'abc123'
```

**Solution:**

Get your numeric Telegram user ID:
1. Message [@userinfobot](https://t.me/userinfobot)
2. Copy the numeric ID (e.g., `123456789`)
3. Update .env:
   ```
   TELEGRAM_ALLOWED_USER_IDS=123456789
   ```

For multiple users:
```
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321,555555555
```

---

### Proxy support (HTTP/HTTPS only)

**When to use:** Running behind a corporate proxy or in a restricted network where outbound HTTP/HTTPS must go through a proxy.

**Supported:** All HTTP and HTTPS requests (Gamma API, CLOB, Binance, Polygon RPC, fetchers) use **httpx**, which respects standard environment variables:

- `HTTPS_PROXY` – proxy for HTTPS requests (e.g. `https://gamma-api.polymarket.com`)
- `HTTP_PROXY` – proxy for HTTP requests
- `ALL_PROXY` – fallback for both
- `NO_PROXY` – comma-separated hosts to bypass (e.g. `localhost,127.0.0.1`)

**Example:**
```bash
export HTTPS_PROXY=http://127.0.0.1:8080
# or in .env:
# HTTPS_PROXY=http://127.0.0.1:8080
```

**Limitation:** WebSocket connections (Polymarket live data, Chainlink Polygon WSS) do **not** currently use these proxy settings. If you need WSS through a proxy, use a system-level proxy or tunnel, or rely on the Chainlink HTTP fallback (Polygon RPC) which does use the proxy.

---

## Data Fetcher Errors

### Live data (/api/live-data): 451, 429, DNS, no_api_key

When calling `GET /api/live-data`, some sources may return errors:

| Error | Source | Cause | Fix |
|-------|--------|--------|-----|
| **451** | `price_ma`, `funding` | Binance blocks your region (e.g. US/UK). | The app now uses **CoinGecko** (price_ma) and **Bybit** (funding) as fallbacks when Binance returns 451. Restart and try again. |
| **429 Too Many Requests** | `dxy` | Yahoo Finance rate limit. | The DXY fetcher retries up to 3 times with 10s backoff. Call `/api/live-data` less often, or set `WEIGHT_DXY=0` to disable. |
| **nodename nor servname provided, or not known** | `etf_flows` | ETF flows API hostname does not resolve (wrong or down). | Set a working URL in .env: `ETF_FLOWS_URL=https://...` or disable: `WEIGHT_ETF_FLOWS=0`. |
| **invalid_etf_flows_url** | `etf_flows` | `ETF_FLOWS_URL` is empty or has no host (e.g. `https://`). | Set a full URL: `ETF_FLOWS_URL=https://api.example.com/etf-flows` or remove it to use the default. |
| **no_api_key** | `exchange_netflow` | CryptoQuant/Glassnode key not set. | Optional: set `CRYPTOQUANT_API_KEY=...` or disable: `WEIGHT_EXCHANGE_NETFLOW=0`. |

Working sources (fear_greed, macro) will still return data; the signal engine uses partial data when some fetchers fail.

---

### ETF Flows Returning Error

**Symptom:**
```
etf_flows: [Errno 8] nodename nor servname provided, or not known
```
or `API endpoint not available`.

**Explanation:**
The default ETF flows URL may be wrong or the service may have moved.

**Workarounds:**

1. **Set a working URL** (if you have one):
   ```bash
   ETF_FLOWS_URL=https://your-working-etf-api.example/api/etf-flows
   ```

2. **Disable the fetcher** (signal uses other sources):
   ```bash
   WEIGHT_ETF_FLOWS=0
   ```

---

### Exchange Netflow Requires Paid API

**Symptom:**
```
fetcher_failed: source=exchange_netflow, error=API key required
```

**Explanation:**
Exchange netflow data requires a paid CryptoQuant or Glassnode API key.

**Solutions:**

**1. Get API key** (recommended for production):
- Sign up at [CryptoQuant](https://cryptoquant.com) or [Glassnode](https://glassnode.com)
- Add to .env:
  ```
  CRYPTOQUANT_API_KEY=your_key_here
  ```

**2. Disable fetcher** (for testing):
  ```bash
  WEIGHT_EXCHANGE_NETFLOW=0
  ```

---

### Circuit Breaker Open

**Symptom:**
```
circuit_open: source=dxy, failures=3
```

**Explanation:**
After 3 consecutive failures, the circuit breaker opens for 5 minutes to prevent cascading failures.

**What to do:**
- **Wait 5 minutes** - circuit auto-closes
- **Check if external API is down** - visit the API URL in browser
- **Increase failure threshold** (if API is flaky):
  ```bash
  CIRCUIT_FAILURE_THRESHOLD=5  # default: 3
  CIRCUIT_OPEN_SECONDS=600      # 10 minutes
  ```

---

## Runtime Errors

### Port Already in Use

**Symptom:**
```
ERROR: [Errno 48] Address already in use
```

**Solution:**

**Find what's using port 8000:**
```bash
lsof -i :8000
# Kill the process
kill -9 <PID>
```

**Or use a different port:**
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
```

---

### Import Error: No module named 'app'

**Symptom:**
```
ModuleNotFoundError: No module named 'app'
```

**Solution:**

**Make sure you're in the project root:**
```bash
cd /path/to/cryptosignal
```

**Reinstall dependencies:**
```bash
uv sync --all-extras
```

**Check PYTHONPATH:**
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

---

### Health Check Returns 503

**Symptom:**
```json
{"status": "unavailable", "db": "disconnected"}
```

**Diagnosis:**

**1. Check database connection:**
```bash
psql "$DATABASE_URL"
```

**2. Check database pool in logs:**
Look for:
```
db_pool_init_failed: error=...
```

**3. Verify DATABASE_URL:**
```bash
echo $DATABASE_URL
# or in .env
cat .env | grep DATABASE_URL
```

**4. Restart app:**
```bash
# If using dev.sh, press Ctrl+C and restart
./scripts/dev.sh

# If using docker-compose
docker-compose restart app
```

---

## Migration Problems

### Migrations Out of Order

**Symptom:**
```
ERROR: column "asset" already exists
```

**Cause:**
Trying to apply migration 002 when baseline already included it.

**Solution:**

**Check migration status:**
```bash
uv run python scripts/init_db.py --status
```

**Skip problematic migration** by marking it as applied:
```bash
psql "$DATABASE_URL" -c \
  "INSERT INTO schema_migrations (version, description) VALUES ('002', 'add_asset') ON CONFLICT DO NOTHING;"
```

**Or drop and recreate** (⚠️ **DESTRUCTIVE**):
```bash
psql -U postgres -c "DROP DATABASE cryptosignal;"
psql -U postgres -c "CREATE DATABASE cryptosignal;"
./scripts/setup.sh
```

---

### Migration Failed Mid-Way

**Symptom:**
```
ERROR: syntax error in migration
```

**Recovery:**

**1. Check which migrations were applied:**
```bash
psql "$DATABASE_URL" -c "SELECT * FROM schema_migrations ORDER BY id;"
```

**2. Fix the SQL file** and re-run:
```bash
uv run python scripts/init_db.py
```

**3. If table is in bad state**, rollback manually:
```bash
psql "$DATABASE_URL"
-- Undo the changes manually
-- e.g., ALTER TABLE signal_runs DROP COLUMN bad_column;
\q

# Delete failed migration record
psql "$DATABASE_URL" -c "DELETE FROM schema_migrations WHERE version = '004';"

# Re-run
uv run python scripts/init_db.py
```

---

## Getting More Help

### Enable Debug Logging

Edit `src/app/logging_config.py`:
```python
configure_logging(debug=True)  # Change False to True
```

Restart the bot to see detailed logs.

### Check Logs

**Development mode:**
Logs appear in terminal where `dev.sh` is running

**Docker mode:**
```bash
docker-compose logs -f app
```

### Run Health Diagnostics

```bash
# Health endpoint
curl http://localhost:8000/health | jq

# Database status
uv run python scripts/init_db.py --status

# Environment validation
uv run python scripts/validate_env.py --mode all
```

### Still Stuck?

1. **Check existing GitHub issues**: https://github.com/your-repo/issues
2. **Create a new issue** with:
   - Error message (full traceback)
   - Steps to reproduce
   - Environment (OS, Python version, PostgreSQL version)
   - Relevant logs (sanitize secrets!)

---

**Back to:** [Quick Start](./QUICK_START.md) | [Setup Guide](./SETUP_GUIDE.md)
