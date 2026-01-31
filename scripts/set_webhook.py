#!/usr/bin/env python3
"""Set Telegram webhook using TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET from .env."""

import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Load .env from project root
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/set_webhook.py <BASE_URL>")
        print("Example: uv run python scripts/set_webhook.py https://abc123.ngrok.io")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    webhook_url = f"{base_url}/webhook/telegram"

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")

    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)
    if not secret:
        print("❌ TELEGRAM_WEBHOOK_SECRET not set in .env")
        sys.exit(1)

    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    data = f"url={webhook_url}&secret_token={secret}".encode("utf-8")

    req = Request(api_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
            print(f"✅ Webhook set to: {webhook_url}")
            print(body)
    except HTTPError as e:
        print(f"❌ Telegram API error ({e.code}): {e.read().decode()}")
        sys.exit(1)
    except URLError as e:
        print(f"❌ Request failed: {e.reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
