"""Google Sheets client: authenticate and batchUpdate. Requires GOOGLE_APPLICATION_CREDENTIALS or env."""

import os
from typing import Any

from app.logging_config import get_logger

logger = get_logger(__name__)


def _get_credentials() -> Any:
    """Return credentials from env (path to JSON). Lazy import google-auth."""
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not path or not os.path.isfile(path):
        return None
    try:
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(
            path,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
    except ImportError:
        logger.debug("sheets_skip", reason="google-auth not installed")
        return None
    except Exception as e:
        logger.warning("sheets_credentials_failed", error=str(e))
        return None


def sheets_client_available() -> bool:
    """True if credentials and spreadsheet ID are set."""
    creds = _get_credentials()
    sheet_id = os.environ.get("SPREADSHEET_ID")
    return creds is not None and bool(sheet_id)
