import importlib


def test_link_token_rejects_invalid_mode_before_live_access(monkeypatch):
    app_module = importlib.import_module("app")
    monkeypatch.setattr(app_module, "DEMO_MODE", False)
    monkeypatch.setattr(
        app_module,
        "get_db",
        lambda: (_ for _ in ()).throw(AssertionError("database should not open")),
    )
    app_module.app.config.update(TESTING=True)

    response = app_module.app.test_client().post("/api/link-token", json={"mode": "bad"})

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

    response = app_module.app.test_client().post("/api/exchange-token", json={})

    assert response.status_code == 400
