#!/usr/bin/env python3
"""Check Telegram webhook status using TELEGRAM_BOT_TOKEN from .env."""

import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

# Load .env from project root
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    api_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"

    try:
        with urlopen(api_url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except HTTPError as e:
        print(f"❌ Telegram API error ({e.code})")
        print(e.read().decode())
        sys.exit(1)
    except URLError as e:
        print(f"❌ Request failed: {e.reason}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid response: {e}")
        sys.exit(1)

    if not data.get("ok"):
        print("❌ Telegram API returned not OK:", data.get("description", "unknown"))
        sys.exit(1)

    result = data.get("result", {})
    url = result.get("url") or ""
    pending = result.get("pending_update_count", 0)
    allowed_updates = result.get("allowed_updates") or []

    print("\n📡 Telegram webhook status\n")
    if url:
        print(f"  Webhook URL:  {url}")
        print(f"  Pending updates: {pending}")
        if allowed_updates:
            print(f"  Allowed updates: {allowed_updates}")
        print("\n  ✅ Webhook is set. Telegram will POST updates to your server.")
        print("  To test: send /start or /status to your bot in Telegram.")
    else:
        print("  Webhook URL:  (not set)")
        print("\n  ⚠️  No webhook configured. The bot will not receive messages.")
        print("  Set it with: uv run python scripts/set_webhook.py <YOUR_HTTPS_BASE_URL>")
        print("  Example: uv run python scripts/set_webhook.py https://abc123.ngrok-free.app")
    print()


if __name__ == "__main__":
    main()
