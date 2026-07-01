import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"
DB_PATH = DATA_DIR / "worthit.db"
BENEFITS_PATH = CONFIG_DIR / "benefits.yaml"
SETTINGS_PATH = CONFIG_DIR / "settings.yaml"

load_dotenv(BASE_DIR / ".env")

PLAID_CLIENT_ID = os.environ.get("PLAID_CLIENT_ID", "")
PLAID_SECRET = os.environ.get("PLAID_SECRET", "")
PLAID_ENV = os.environ.get("PLAID_ENV", "sandbox")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev")


def load_settings() -> dict:
    defaults = {
        "sync_stale_minutes": 60,
        "at_risk_days_monthly": 7,
        "at_risk_days_semiannual": 21,
    }
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH) as f:
            data = yaml.safe_load(f) or {}
        defaults.update(data)
    return defaults
