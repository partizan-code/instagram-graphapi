import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

APP_ID: str = os.environ.get("APP_ID", "").strip()
APP_SECRET: str = os.environ.get("APP_SECRET", "").strip()

META_CONFIG_ID = os.environ.get("META_CONFIG_ID", "").strip()
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://localhost/").strip()
WEBHOOK_VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "").strip()
GRAPH_BASE = "https://graph.facebook.com"

# requests applies this timeout separately to connection and response reads.
HTTP_TIMEOUT = 30

META_API_VERSION = os.environ.get("META_API_VERSION", "v27.0").strip()
INSTAGRAM_ACCOUNT_ID = os.environ.get("INSTAGRAM_ACCOUNT_ID", "").strip()
DIALOG_LIMIT = 5
HISTORY_LIMIT = 20


def require_app_credentials() -> None:
    """Only OAuth operations need the application ID and secret."""
    if not APP_ID:
        raise KeyError("APP_ID")
    if not APP_SECRET:
        raise KeyError("APP_SECRET")
