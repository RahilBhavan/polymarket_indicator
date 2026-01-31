#!/bin/bash
#
# Set Telegram webhook for CryptoSignal bot.
# Uses TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET from .env.
#
# Usage: ./scripts/setup_webhook.sh <BASE_URL>
# Example: ./scripts/setup_webhook.sh https://abc123.ngrok-free.app
#

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f .env ]; then
    echo "❌ .env not found. Run ./scripts/setup.sh first."
    exit 1
fi

if [ -z "$1" ]; then
    echo "Usage: ./scripts/setup_webhook.sh <BASE_URL>"
    echo ""
    echo "  BASE_URL  Your bot's public HTTPS URL (no trailing slash)."
    echo "            Webhook will be set to: <BASE_URL>/webhook/telegram"
    echo ""
    echo "Examples:"
    echo "  ./scripts/setup_webhook.sh https://abc123.ngrok-free.app"
    echo "  ./scripts/setup_webhook.sh https://your-domain.com"
    echo ""
    echo "Check current webhook: uv run python scripts/check_webhook.py"
    exit 1
fi

echo "Validating environment..."
uv run python scripts/validate_env.py --quiet 2>/dev/null || true

echo ""
uv run python scripts/set_webhook.py "$1"
