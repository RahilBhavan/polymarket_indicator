# Quick Start Guide

Get your CryptoSignal bot running in 5 minutes! ⚡

## Prerequisites

Before you begin, make sure you have:

- ✅ **Python 3.11 or later** ([Download](https://www.python.org/downloads/))
- ✅ **PostgreSQL 15+** ([Installation Guide](./SETUP_GUIDE.md#installing-postgresql))
- ✅ **Telegram Bot Token** (Get from [@BotFather](https://t.me/botfather))
- ✅ **Your Telegram User ID** ([Find it here](https://t.me/userinfobot))

## One-Command Setup

```bash
./scripts/setup.sh
```

That's it! The setup script will:
1. Check your Python version
2. Install the `uv` package manager if needed
3. Create your `.env` configuration file (with interactive prompts)
4. Install all dependencies
5. Initialize your PostgreSQL database
6. Display next steps

## What Happens During Setup

### 1. Configuration
You'll be prompted for:
- **Telegram Bot Token** - Get this from [@BotFather](https://t.me/botfather)
- **Telegram User ID(s)** - Find yours at [@userinfobot](https://t.me/userinfobot)
- **Database URL** - Default: `postgresql://cryptosignal:changeme@localhost:5432/cryptosignal`

The script generates a secure webhook secret automatically.

### 2. Database Initialization
The setup creates:
- PostgreSQL database (if it doesn't exist)
- All required tables
- Indexes for performance
- Migration tracking system

## Running the Bot

### Development Mode
```bash
./scripts/dev.sh
```

This starts the bot with auto-reload. Visit http://localhost:8000/health to verify it's running.

### Production Mode
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or use Docker:
```bash
docker-compose up -d
```

## Setting Up Telegram Webhook

The bot receives messages via webhook. You need HTTPS for this to work.

### For Local Development (using ngrok)

1. Install ngrok: https://ngrok.com/download
2. Start your bot: `./scripts/dev.sh`
3. In another terminal: `ngrok http 8000`
4. Copy the HTTPS URL from ngrok (e.g., `https://abc123.ngrok.io`)
5. Register webhook:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://abc123.ngrok.io/webhook/telegram" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>"
```

Replace:
- `<YOUR_BOT_TOKEN>` with your actual token from .env
- `<YOUR_WEBHOOK_SECRET>` with the webhook secret from .env
- `abc123.ngrok.io` with your ngrok domain

### For Production

Use your actual domain with HTTPS:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://yourdomain.com/webhook/telegram" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>"
```

## Testing Your Bot

Once webhook is set up, message your bot on Telegram:

```
/start    - Welcome message
/status   - Check bot health
/help     - List all commands
/signal   - Get today's trading signal
```

## Common Issues

### "Database connection failed"
- **Fix**: Make sure PostgreSQL is running: `pg_ctl status`
- **macOS**: `brew services start postgresql@15`
- **Linux**: `sudo systemctl start postgresql`

### "Telegram webhook not working"
- **Fix**: Verify webhook is registered:
  ```bash
  curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
  ```
- Must use HTTPS (use ngrok for local dev)
- Check webhook secret matches your .env

### "Python version too old"
- **Fix**: Upgrade to Python 3.11+
- **macOS**: `brew install python@3.11`
- **Ubuntu**: `sudo apt install python3.11`

### Need more help?
See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for detailed solutions.

## Next Steps

Now that your bot is running:

1. **Configure settings**: `/settings` in Telegram to set bankroll, verbosity
2. **Test signals**: `/signal` to get a signal (market must be available)
3. **View analytics**: `/stats` to see win rate and performance
4. **Set up cron jobs**: For daily signals and EOD outcome recording
5. **Read the docs**:
   - [Setup Guide](./SETUP_GUIDE.md) - Detailed configuration options
   - [Architecture](./ARCHITECTURE.md) - How the bot works
   - [Development Guide](./DEVELOPMENT.md) - Contributing and customization

## Daily Operations

### Manual Signal Generation
```bash
curl -X POST "http://localhost:8000/internal/run-daily-signal" \
  -H "X-Cron-Secret: <YOUR_EOD_CRON_SECRET>"
```

### Live Data for Analysis
Fetch current values from all data sources (ETF flows, price/MA, funding, DXY, Fear & Greed, etc.) without running a full signal:

```bash
# If EOD_CRON_SECRET is set in .env:
curl -H "X-Cron-Secret: <YOUR_EOD_CRON_SECRET>" "http://localhost:8000/api/live-data"

# If EOD_CRON_SECRET is unset (local dev), no header needed:
curl http://localhost:8000/api/live-data
```

Returns JSON: `{ "timestamp": "...", "sources": [ { "source_id", "raw_value", "normalized_score", "stale", "error" }, ... ] }`. Same data feeds the signal engine.

### Check Health
```bash
curl http://localhost:8000/health
```

### View Logs
```bash
# If running via dev.sh, logs appear in terminal
# If running via docker-compose:
docker-compose logs -f app
```

## Stopping the Bot

### Development Mode
Press `Ctrl+C` in the terminal where `dev.sh` is running.

### Docker Mode
```bash
docker-compose down
```

---

**Ready to dive deeper?** Check out the [Setup Guide](./SETUP_GUIDE.md) for advanced configuration options.

**Having trouble?** See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for solutions to common problems.
