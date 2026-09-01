import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"
BENEFITS_PATH = CONFIG_DIR / "benefits.yaml"
SETTINGS_PATH = CONFIG_DIR / "settings.yaml"

load_dotenv(BASE_DIR / ".env")


def _env_flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


PLAID_CLIENT_ID = os.environ.get("PLAID_CLIENT_ID", "")
PLAID_ENV = os.environ.get("PLAID_ENV", "sandbox").strip().lower()
if PLAID_ENV not in ("sandbox", "production"):
    raise ValueError("PLAID_ENV must be either 'sandbox' or 'production'")
DB_PATH = DATA_DIR / f"worthit-{PLAID_ENV}.db"
_PLAID_SECRET_SUFFIX = "PROD" if PLAID_ENV == "production" else "SANDBOX"
PLAID_SECRET = os.environ.get(
    f"PLAID_SECRET_{_PLAID_SECRET_SUFFIX}",
    os.environ.get("PLAID_SECRET", ""),
)
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev")
FLASK_DEBUG = _env_flag("FLASK_DEBUG")

# Demo mode never touches the database or Plaid - it renders mock data so the
# public deployment never has a path to real financial data, even if real
# Plaid keys happen to be present in the environment.
DEMO_MODE = _env_flag("DEMO_MODE")


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
