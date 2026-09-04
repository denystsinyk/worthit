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
_DB_ENV = PLAID_ENV if PLAID_ENV in ("sandbox", "production") else "invalid"
DB_PATH = DATA_DIR / f"worthit-{_DB_ENV}.db"
_PLAID_SECRET_SUFFIX = "PROD" if PLAID_ENV == "production" else "SANDBOX"
PLAID_SECRET = os.environ.get(
    f"PLAID_SECRET_{_PLAID_SECRET_SUFFIX}",
    os.environ.get("PLAID_SECRET", ""),
)
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev")
FLASK_DEBUG = _env_flag("FLASK_DEBUG")
PLAID_WEBHOOK_URL = os.environ.get("PLAID_WEBHOOK_URL", "").strip()
PLAID_WEBHOOK_SECRET = os.environ.get("PLAID_WEBHOOK_SECRET", "").strip()

# Demo mode never touches the database or Plaid - it renders mock data so the
# public deployment never has a path to real financial data, even if real
# Plaid keys happen to be present in the environment.
DEMO_MODE = _env_flag("DEMO_MODE")


class ConfigurationError(RuntimeError):
    pass


def runtime_config_errors(
    *,
    plaid_env: str = PLAID_ENV,
    plaid_client_id: str = PLAID_CLIENT_ID,
    plaid_secret: str = PLAID_SECRET,
    flask_secret_key: str = FLASK_SECRET_KEY,
    flask_debug: bool = FLASK_DEBUG,
    demo_mode: bool = DEMO_MODE,
) -> list[str]:
    errors = []
    if plaid_env not in ("sandbox", "production"):
        errors.append("PLAID_ENV must be 'sandbox' or 'production'.")
    if not flask_secret_key or flask_secret_key in ("dev", "change-me"):
        errors.append("FLASK_SECRET_KEY must be changed from the example value.")
    if flask_debug:
        errors.append("FLASK_DEBUG must be false for the supported runtime.")
    if not demo_mode:
        if not plaid_client_id:
            errors.append("PLAID_CLIENT_ID is required when DEMO_MODE=false.")
        if not plaid_secret:
            suffix = "PROD" if plaid_env == "production" else "SANDBOX"
            errors.append(f"PLAID_SECRET_{suffix} is required when DEMO_MODE=false.")
    return errors


def validate_runtime_config() -> None:
    errors = runtime_config_errors()
    if errors:
        formatted = "\n".join(f"- {error}" for error in errors)
        raise ConfigurationError(f"WorthIt configuration is invalid:\n{formatted}")


def load_settings() -> dict:
    defaults = {
        "sync_stale_minutes": 60,
        "at_risk_days_monthly": 7,
        "at_risk_days_semiannual": 21,
        "annual_fee": 325,
        "transaction_history_days": 730,
    }
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH) as f:
            data = yaml.safe_load(f) or {}
        defaults.update(data)
    return defaults
