#!/usr/bin/env python3
"""Validate environment variables for CryptoSignal bot."""

import os
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

# Load .env from project root so os.getenv() sees values when run as script or at app startup
try:
    from dotenv import load_dotenv
    _project_root = Path(__file__).resolve().parent.parent
    load_dotenv(_project_root / ".env")
except ImportError:
    pass  # dotenv not installed; rely on process environment


class ValidationError(Exception):
    """Raised when environment validation fails."""
    pass


def validate_env(mode: Literal["required", "all"] = "required") -> dict[str, str]:
    """
    Validate environment variables.

    Args:
        mode: "required" checks only critical vars, "all" checks everything

    Returns:
        dict of validated environment variables

    Raises:
        ValidationError: if validation fails
    """
    errors = []
    warnings = []
    env = {}

    # Required variables
    required_vars = {
        "TELEGRAM_BOT_TOKEN": _validate_telegram_token,
        "TELEGRAM_WEBHOOK_SECRET": _validate_webhook_secret,
        "TELEGRAM_ALLOWED_USER_IDS": _validate_user_ids,
        "DATABASE_URL": _validate_database_url,
    }

    # Optional but recommended variables
    recommended_vars = {
        "EOD_CRON_SECRET": lambda x: _validate_min_length(x, 16, "EOD_CRON_SECRET"),
        "ADMIN_CHAT_ID": _validate_chat_id,
    }

    # Check required variables
    for var_name, validator in required_vars.items():
        value = os.getenv(var_name)
        if not value:
            errors.append(f"❌ {var_name} is required but not set")
            continue

        try:
            validated = validator(value)
            env[var_name] = validated
        except ValueError as e:
            errors.append(f"❌ {var_name}: {e}")

    # Check recommended variables (only warnings)
    if mode == "all":
        for var_name, validator in recommended_vars.items():
            value = os.getenv(var_name)
            if not value:
                warnings.append(f"⚠️  {var_name} is not set (recommended for production)")
                continue

            try:
                validated = validator(value)
                env[var_name] = validated
            except ValueError as e:
                warnings.append(f"⚠️  {var_name}: {e}")

    # Report results
    if errors:
        print("\n❌ Environment Validation Failed:\n")
        for error in errors:
            print(f"  {error}")
        print()
        raise ValidationError(f"{len(errors)} validation error(s)")

    if warnings:
        print("\n⚠️  Environment Warnings:\n")
        for warning in warnings:
            print(f"  {warning}")
        print()

    return env


def _validate_telegram_token(value: str) -> str:
    """Validate Telegram bot token format."""
    if not value or len(value) < 20:
        raise ValueError("Invalid token (too short)")
    if ":" not in value:
        raise ValueError("Invalid token format (should be 'BOT_ID:TOKEN')")

    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("Invalid token format")

    bot_id, token = parts
    if not bot_id.isdigit():
        raise ValueError("Bot ID should be numeric")
    if len(token) < 20:
        raise ValueError("Token part too short")

    return value


def _validate_webhook_secret(value: str) -> str:
    """Validate webhook secret strength."""
    if len(value) < 32:
        raise ValueError(
            f"Webhook secret too short ({len(value)} chars, minimum 32 recommended for security)"
        )
    return value


def _validate_user_ids(value: str) -> str:
    """Validate comma-separated Telegram user IDs."""
    ids = [x.strip() for x in value.split(",") if x.strip()]
    if not ids:
        raise ValueError("At least one user ID required")

    for user_id in ids:
        if not user_id.isdigit():
            raise ValueError(f"Invalid user ID '{user_id}' (must be numeric)")
        if len(user_id) < 5:
            raise ValueError(f"Invalid user ID '{user_id}' (too short)")

    return value


def _validate_database_url(value: str) -> str:
    """Validate PostgreSQL connection URL."""
    if not value.startswith(("postgresql://", "postgres://")):
        raise ValueError("Must start with 'postgresql://' or 'postgres://'")

    try:
        parsed = urlparse(value)
        if not parsed.hostname:
            raise ValueError("Missing hostname")
        if not parsed.path or parsed.path == "/":
            raise ValueError("Missing database name in path")
    except Exception as e:
        raise ValueError(f"Invalid URL format: {e}")

    return value


def _validate_chat_id(value: str) -> str:
    """Validate Telegram chat ID."""
    # Chat IDs can be negative for groups
    if not value.lstrip("-").isdigit():
        raise ValueError("Chat ID must be numeric (can be negative for groups)")
    return value


def _validate_min_length(value: str, min_len: int, var_name: str) -> str:
    """Validate minimum length."""
    if len(value) < min_len:
        raise ValueError(f"{var_name} should be at least {min_len} characters")
    return value


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate CryptoSignal environment variables")
    parser.add_argument(
        "--mode",
        choices=["required", "all"],
        default="required",
        help="Validation mode (required=critical vars only, all=include recommendations)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress success message",
    )

    args = parser.parse_args()

    try:
        env = validate_env(mode=args.mode)
        if not args.quiet:
            print(f"\n✅ Environment validation passed ({len(env)} variables validated)\n")
        sys.exit(0)
    except ValidationError as e:
        print(f"\n{e}\n")
        print("💡 Tip: Copy .env.example to .env and fill in the required values")
        print("   See docs/SETUP_GUIDE.md for detailed setup instructions\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
