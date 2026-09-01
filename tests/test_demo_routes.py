import importlib

import pytest


@pytest.fixture
def demo_app(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", True)

    def forbidden(*args, **kwargs):
        raise AssertionError("demo mode touched a live-data dependency")

    monkeypatch.setattr(app_module, "get_db", forbidden)
    monkeypatch.setattr(app_module.sync, "run_sync", forbidden)
    monkeypatch.setattr(app_module.plaid_client, "create_link_token", forbidden)
    monkeypatch.setattr(app_module.plaid_client, "exchange_public_token", forbidden)
    app_module.app.config.update(TESTING=True)
    return app_module.app


def test_demo_dashboard_does_not_touch_database_or_plaid(demo_app):
    response = demo_app.test_client().get("/")

    assert response.status_code == 200
    assert b"mock data only" in response.data


@pytest.mark.parametrize(
    "path",
    ["/api/link-token", "/api/exchange-token", "/api/reauth-complete"],
)
def test_demo_plaid_api_routes_are_forbidden(demo_app, path):
    response = demo_app.test_client().post(path, json={})

    assert response.status_code == 403


@pytest.mark.parametrize("path", ["/link", "/reauth", "/sync"])
def test_demo_ui_actions_redirect_without_live_access(demo_app, path):
    method = demo_app.test_client().post if path == "/sync" else demo_app.test_client().get
    response = method(path)

    assert response.status_code == 302
