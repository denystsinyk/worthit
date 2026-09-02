import pytest

from worthit.config import ConfigurationError, runtime_config_errors, validate_runtime_config


def _errors(**overrides):
    values = {
        "plaid_env": "sandbox",
        "plaid_client_id": "client-id",
        "plaid_secret": "secret",
        "flask_secret_key": "strong-secret",
        "flask_debug": False,
        "demo_mode": False,
    }
    values.update(overrides)
    return runtime_config_errors(**values)


def test_valid_sandbox_and_production_configs():
    assert _errors() == []
    assert _errors(plaid_env="production") == []


def test_demo_does_not_require_plaid_credentials():
    assert _errors(demo_mode=True, plaid_client_id="", plaid_secret="") == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"plaid_env": "staging"}, "PLAID_ENV"),
        ({"plaid_client_id": ""}, "PLAID_CLIENT_ID"),
        ({"plaid_secret": ""}, "PLAID_SECRET_SANDBOX"),
        ({"flask_secret_key": "change-me"}, "FLASK_SECRET_KEY"),
        ({"flask_debug": True}, "FLASK_DEBUG"),
    ],
)
def test_invalid_runtime_config(overrides, message):
    assert any(message in error for error in _errors(**overrides))


def test_validator_raises_with_actionable_message(monkeypatch):
    monkeypatch.setattr(
        "worthit.config.runtime_config_errors",
        lambda: ["PLAID_CLIENT_ID is required when DEMO_MODE=false."],
    )

    with pytest.raises(ConfigurationError, match="PLAID_CLIENT_ID"):
        validate_runtime_config()
