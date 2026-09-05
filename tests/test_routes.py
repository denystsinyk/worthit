import importlib
from datetime import datetime, timedelta, timezone

from worthit.sync import SyncSummary


def csrf_headers(client):
    with client.session_transaction() as session:
        session["csrf_token"] = "test-csrf-token"
    return {"X-CSRF-Token": "test-csrf-token"}


def configure_live_dashboard(monkeypatch, *, last_error=None):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", False)
    connection = object()
    state = {
        "item_id": "item-1",
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
        "last_error": last_error,
    }
    monkeypatch.setattr(app_module, "get_db", lambda: connection)
    monkeypatch.setattr(app_module.models, "get_sync_state", lambda conn: state)
    monkeypatch.setattr(app_module.models, "get_transactions", lambda conn, start, end: [])
    monkeypatch.setattr(app_module.models, "get_all_transactions", lambda conn: [])
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    return app_module


def test_link_token_rejects_invalid_mode_before_live_access(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", False)
    monkeypatch.setattr(
        app_module,
        "get_db",
        lambda: (_ for _ in ()).throw(AssertionError("database should not open")),
    )
    app_module.app.config.update(TESTING=True)

    client = app_module.app.test_client()
    response = client.post("/api/link-token", json={"mode": "bad"}, headers=csrf_headers(client))

    assert response.status_code == 400


def test_exchange_token_requires_string_before_live_access(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", False)
    monkeypatch.setattr(
        app_module,
        "get_db",
        lambda: (_ for _ in ()).throw(AssertionError("database should not open")),
    )
    app_module.app.config.update(TESTING=True)

    client = app_module.app.test_client()
    response = client.post("/api/exchange-token", json={}, headers=csrf_headers(client))

    assert response.status_code == 400


def test_demo_analytics_page_renders(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", True)
    app_module.app.config.update(TESTING=True)

    response = app_module.app.test_client().get("/analytics?range=12m")

    assert response.status_code == 200
    assert b"Value by month" in response.data
    assert b"Benefit performance" in response.data
    assert b'class="bar-stack"' in response.data
    assert b'class="series-uber" style="height:' in response.data


def test_force_sync_reports_changes_and_returns_to_dashboard(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", False)
    monkeypatch.setattr(app_module, "get_db", lambda: object())
    monkeypatch.setattr(
        app_module.sync,
        "run_sync",
        lambda conn: [SyncSummary("item-1", added=2, modified=1, removed=3)],
    )
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    client = app_module.app.test_client()

    response = client.post("/sync", headers=csrf_headers(client), follow_redirects=False)

    assert response.status_code == 302
    with client.session_transaction() as session:
        assert "2 added, 1 updated, 3 removed" in session["_flashes"][0][1]


def test_live_dashboard_renders_refresh_button(monkeypatch):
    app_module = configure_live_dashboard(monkeypatch)

    response = app_module.app.test_client().get("/")

    assert response.status_code == 200
    assert b"Refresh now" in response.data
    assert b'action="/sync"' in response.data


def test_live_dashboard_renders_sync_error_and_keeps_refresh_available(monkeypatch):
    app_module = configure_live_dashboard(monkeypatch, last_error="PLAID_NETWORK_ERROR")

    response = app_module.app.test_client().get("/")

    assert b"Sync unavailable" in response.data
    assert b"PLAID_NETWORK_ERROR" in response.data
    assert b"Refresh now" in response.data


def test_force_sync_flashes_error_code(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", False)
    monkeypatch.setattr(app_module, "get_db", lambda: object())
    monkeypatch.setattr(
        app_module.sync,
        "run_sync",
        lambda conn: [SyncSummary("item-1", error="PLAID_NETWORK_ERROR")],
    )
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    client = app_module.app.test_client()

    client.post("/sync", headers=csrf_headers(client))

    with client.session_transaction() as session:
        assert "PLAID_NETWORK_ERROR" in session["_flashes"][0][1]


def test_plaid_webhook_syncs_known_item(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "PLAID_WEBHOOK_SECRET", "test-webhook-secret")
    connection = object()
    monkeypatch.setattr(app_module, "get_db", lambda: connection)
    monkeypatch.setattr(app_module.models, "get_sync_state", lambda conn: {"item_id": "item-1"})
    calls = []
    monkeypatch.setattr(app_module.sync, "run_sync", lambda conn: calls.append(conn))
    app_module.app.config.update(TESTING=True)

    response = app_module.app.test_client().post(
        "/api/plaid-webhook/test-webhook-secret",
        json={
            "webhook_type": "TRANSACTIONS",
            "webhook_code": "SYNC_UPDATES_AVAILABLE",
            "item_id": "item-1",
        },
    )

    assert response.status_code == 200
    assert calls == [connection]


def test_plaid_webhook_rejects_wrong_secret(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "PLAID_WEBHOOK_SECRET", "right-secret")
    app_module.app.config.update(TESTING=True)

    response = app_module.app.test_client().post("/api/plaid-webhook/wrong-secret", json={})

    assert response.status_code == 404


def test_reset_removes_plaid_item_before_local_cache(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", False)
    monkeypatch.setattr(app_module, "get_db", lambda: object())
    monkeypatch.setattr(
        app_module.models,
        "get_sync_state",
        lambda conn: {"item_id": "item-1", "access_token": "access-1"},
    )
    calls = []
    monkeypatch.setattr(app_module.plaid_client, "remove_item", lambda token: calls.append(("plaid", token)))
    monkeypatch.setattr(app_module.models, "clear_item", lambda conn, item: calls.append(("local", item)))
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret")
    client = app_module.app.test_client()

    client.get("/connection/reset")
    with client.session_transaction() as session:
        token = session["reset_token"]
    response = client.post(
        "/connection/reset",
        data={"reset_token": token, "csrf_token": session["csrf_token"]},
    )

    assert response.status_code == 302
    assert calls == [("plaid", "access-1"), ("local", "item-1")]


def test_reset_rejects_missing_confirmation(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", False)
    monkeypatch.setattr(app_module, "get_db", lambda: object())
    monkeypatch.setattr(
        app_module.models,
        "get_sync_state",
        lambda conn: {"item_id": "item-1", "access_token": "access-1"},
    )
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret")

    client = app_module.app.test_client()
    response = client.post("/connection/reset", data={}, headers=csrf_headers(client))

    assert response.status_code == 400


def test_mutation_rejects_missing_csrf_token(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", False)
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret")

    response = app_module.app.test_client().post("/sync")

    assert response.status_code == 403


def test_sync_time_is_timezone_aware_and_friendly(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "APP_TIMEZONE", "America/New_York")
    value = (datetime.now(timezone.utc) - timedelta(minutes=4)).isoformat()

    formatted = app_module.format_sync_time(value)

    assert formatted["relative"] == "4m ago"
    assert formatted["absolute"].endswith(("EDT", "EST"))


def test_demo_status_page_renders_without_private_data(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", True)
    app_module.app.config.update(TESTING=True, SECRET_KEY="test-secret")

    response = app_module.app.test_client().get("/status")

    assert response.status_code == 200
    assert b"Connection status" in response.data
    assert b"Sample data" in response.data


def test_demo_csv_export_has_safe_columns(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", True)
    app_module.app.config.update(TESTING=True)

    response = app_module.app.test_client().get("/export.csv")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert b"matched_benefits" in response.data
    assert b"access_token" not in response.data
    assert b"raw_json" not in response.data
