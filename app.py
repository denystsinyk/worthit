import hmac
import secrets
from datetime import date, datetime, timedelta

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for

from worthit import analytics, db, demo_data, models, plaid_client, sync
from worthit.benefits import status
from worthit.benefits.loader import load_benefits
from worthit.benefits.periods import current_period
from worthit.benefits.schema import BenefitConfig
from worthit.config import (
    BENEFITS_PATH,
    DEMO_MODE,
    FLASK_DEBUG,
    FLASK_SECRET_KEY,
    PLAID_ENV,
    load_settings,
    validate_runtime_config,
)

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

DEMO_DISABLED_MESSAGE = (
    "This is a demo with mock data - that action is disabled here. "
    "See README.md for instructions on running this yourself with your own Amex account."
)


def get_db():
    if "db" not in g:
        g.db = db.get_conn()
        db.init_db(g.db)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.route("/healthz")
def healthz():
    mode = "demo" if DEMO_MODE else PLAID_ENV
    return jsonify({"status": "ok", "mode": mode})


def _is_stale(last_synced_at: str | None, stale_minutes: int) -> bool:
    if not last_synced_at:
        return True
    last = datetime.fromisoformat(last_synced_at)
    return (datetime.now() - last) > timedelta(minutes=stale_minutes)


def _compute_lookback_start(benefits: list[BenefitConfig], today: date) -> date:
    starts = []
    for b in benefits:
        period_start, _ = current_period(b, today)
        starts.append(period_start)
        if b.posting_lag_days:
            starts.append(today - timedelta(days=b.posting_lag_days))
    return min(starts) if starts else today


def _dashboard_summary(statuses) -> dict:
    return {
        "used": sum(s.amount_used for s in statuses),
        "available": sum(s.amount_total for s in statuses),
        "complete": sum(s.state == "complete" for s in statuses),
        "attention": sum(s.state == "at_risk" for s in statuses),
    }


@app.route("/")
def dashboard():
    settings = load_settings()
    today = date.today()
    benefits = load_benefits(BENEFITS_PATH)

    if DEMO_MODE:
        # Never touches the database or Plaid - purely in-memory mock data.
        # Widen the semiannual at-risk window so the Resy posting-lag "pending"
        # state reliably shows up regardless of where we are in the real
        # 6-month period (it would otherwise only trigger in the last few
        # weeks of each half, since Resy's mock purchase is 10 days old).
        demo_settings = {**settings, "at_risk_days_semiannual": 200}
        all_txns = demo_data.build_demo_transactions(today)
        statuses = [status.compute_status(b, all_txns, today, demo_settings) for b in benefits]
        report = analytics.build_report(benefits, all_txns, today, demo_settings, "ytd")
        return render_template(
            "dashboard.html",
            statuses=statuses,
            summary=_dashboard_summary(statuses),
            linked=True,
            reconnect_needed=False,
            sync_state=None,
            demo_mode=True,
            analytics_summary=report,
        )

    conn = get_db()
    sync_state = models.get_sync_state(conn)
    reconnect_needed = bool(sync_state and sync_state["last_error"] == "ITEM_LOGIN_REQUIRED")

    if sync_state and not reconnect_needed and _is_stale(sync_state["last_synced_at"], settings["sync_stale_minutes"]):
        sync.run_sync(conn)
        sync_state = models.get_sync_state(conn)
        reconnect_needed = bool(sync_state and sync_state["last_error"] == "ITEM_LOGIN_REQUIRED")

    lookback_start = _compute_lookback_start(benefits, today)
    all_txns = models.get_transactions(conn, lookback_start, today)
    statuses = [status.compute_status(b, all_txns, today, settings) for b in benefits]
    report = analytics.build_report(
        benefits, models.get_all_transactions(conn), today, settings, "ytd"
    )

    return render_template(
        "dashboard.html",
        statuses=statuses,
        summary=_dashboard_summary(statuses),
        linked=bool(sync_state),
        reconnect_needed=reconnect_needed,
        sync_state=sync_state,
        sync_error=(
            sync_state["last_error"]
            if sync_state and sync_state["last_error"] != "ITEM_LOGIN_REQUIRED"
            else None
        ),
        demo_mode=False,
        analytics_summary=report,
    )


@app.route("/analytics")
def analytics_page():
    settings = load_settings()
    today = date.today()
    benefits = load_benefits(BENEFITS_PATH)
    range_key = request.args.get("range", "ytd")
    if DEMO_MODE:
        transactions = demo_data.build_demo_transactions(today)
        linked = True
    else:
        conn = get_db()
        linked = bool(models.get_sync_state(conn))
        transactions = models.get_all_transactions(conn)
    report = analytics.build_report(benefits, transactions, today, settings, range_key)
    return render_template(
        "analytics.html", report=report, benefits=benefits, linked=linked, demo_mode=DEMO_MODE
    )


@app.route("/sync", methods=["POST"])
def force_sync():
    if DEMO_MODE:
        flash(DEMO_DISABLED_MESSAGE)
        return redirect(url_for("dashboard"))
    conn = get_db()
    sync.run_sync(conn)
    return redirect(url_for("dashboard"))


@app.route("/link")
def link_page():
    if DEMO_MODE:
        flash(DEMO_DISABLED_MESSAGE)
        return redirect(url_for("dashboard"))
    return render_template("link.html")


@app.route("/reauth")
def reauth_page():
    if DEMO_MODE:
        flash(DEMO_DISABLED_MESSAGE)
        return redirect(url_for("dashboard"))
    return render_template("reauth.html")


@app.route("/connection/reset", methods=["GET", "POST"])
def reset_connection():
    if DEMO_MODE:
        flash(DEMO_DISABLED_MESSAGE)
        return redirect(url_for("dashboard"))
    conn = get_db()
    state = models.get_sync_state(conn)
    if not state:
        return redirect(url_for("link_page"))
    if request.method == "GET":
        token = secrets.token_urlsafe(24)
        session["reset_token"] = token
        return render_template("reset.html", reset_token=token)

    expected = session.pop("reset_token", "")
    supplied = request.form.get("reset_token", "")
    if not expected or not hmac.compare_digest(expected, supplied):
        return "Invalid or expired confirmation", 400
    try:
        plaid_client.remove_item(state["access_token"])
    except plaid_client.PlaidSyncError as exc:
        flash(f"Could not remove the Plaid connection: {exc.code}")
        return redirect(url_for("reset_connection"))
    models.clear_item(conn, state["item_id"])
    flash("Connection removed. Link again to request up to two years of history.")
    return redirect(url_for("link_page"))


@app.route("/api/link-token", methods=["POST"])
def api_link_token():
    if DEMO_MODE:
        return jsonify({"error": "disabled in demo mode"}), 403
    mode = (request.get_json(silent=True) or {}).get("mode", "link")
    if mode not in ("link", "update"):
        return jsonify({"error": "mode must be 'link' or 'update'"}), 400
    conn = get_db()
    access_token = None
    if mode == "update":
        state = models.get_sync_state(conn)
        if not state:
            return jsonify({"error": "no linked Item to update"}), 409
        access_token = state["access_token"]
    link_token = plaid_client.create_link_token(access_token=access_token)
    return jsonify({"link_token": link_token})


@app.route("/api/exchange-token", methods=["POST"])
def api_exchange_token():
    if DEMO_MODE:
        return jsonify({"error": "disabled in demo mode"}), 403
    public_token = (request.get_json(silent=True) or {}).get("public_token")
    if not public_token or not isinstance(public_token, str):
        return jsonify({"error": "public_token is required"}), 400
    conn = get_db()
    access_token, item_id = plaid_client.exchange_public_token(public_token)
    models.upsert_sync_state(conn, item_id, access_token)
    return jsonify({"status": "ok"})


@app.route("/api/reauth-complete", methods=["POST"])
def api_reauth_complete():
    if DEMO_MODE:
        return jsonify({"error": "disabled in demo mode"}), 403
    # Plaid Link's "update mode" refreshes credentials for the existing Item in
    # place - there's no new access_token to exchange, we just clear the error.
    conn = get_db()
    state = models.get_sync_state(conn)
    if state:
        models.update_sync_progress(conn, state["item_id"], state["cursor"], None)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    validate_runtime_config()
    app.run(debug=FLASK_DEBUG)
