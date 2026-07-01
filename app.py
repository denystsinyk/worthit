from datetime import date, datetime, timedelta

from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for

from worthit import db, models, plaid_client, sync
from worthit.benefits import status
from worthit.benefits.loader import load_benefits
from worthit.benefits.periods import current_period
from worthit.benefits.schema import BenefitConfig
from worthit.config import BENEFITS_PATH, FLASK_SECRET_KEY, load_settings

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY


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


@app.route("/")
def dashboard():
    conn = get_db()
    settings = load_settings()
    sync_state = models.get_sync_state(conn)
    reconnect_needed = bool(sync_state and sync_state["last_error"] == "ITEM_LOGIN_REQUIRED")

    if sync_state and not reconnect_needed and _is_stale(sync_state["last_synced_at"], settings["sync_stale_minutes"]):
        sync.run_sync(conn)
        sync_state = models.get_sync_state(conn)
        reconnect_needed = bool(sync_state and sync_state["last_error"] == "ITEM_LOGIN_REQUIRED")

    benefits = load_benefits(BENEFITS_PATH)
    today = date.today()
    lookback_start = _compute_lookback_start(benefits, today)
    all_txns = models.get_transactions(conn, lookback_start, today)
    statuses = [status.compute_status(b, all_txns, today, settings) for b in benefits]
    unreviewed_count = len(models.get_unreviewed_credits(conn))

    return render_template(
        "dashboard.html",
        statuses=statuses,
        linked=bool(sync_state),
        reconnect_needed=reconnect_needed,
        sync_state=sync_state,
        unreviewed_count=unreviewed_count,
    )


@app.route("/sync", methods=["POST"])
def force_sync():
    conn = get_db()
    sync.run_sync(conn)
    return redirect(url_for("dashboard"))


@app.route("/link")
def link_page():
    return render_template("link.html")


@app.route("/reauth")
def reauth_page():
    return render_template("reauth.html")


@app.route("/api/link-token", methods=["POST"])
def api_link_token():
    conn = get_db()
    mode = (request.get_json(silent=True) or {}).get("mode", "link")
    access_token = None
    if mode == "update":
        state = models.get_sync_state(conn)
        if state:
            access_token = state["access_token"]
    link_token = plaid_client.create_link_token(access_token=access_token)
    return jsonify({"link_token": link_token})


@app.route("/api/exchange-token", methods=["POST"])
def api_exchange_token():
    conn = get_db()
    public_token = (request.get_json(silent=True) or {}).get("public_token")
    access_token, item_id = plaid_client.exchange_public_token(public_token)
    models.upsert_sync_state(conn, item_id, access_token)
    return jsonify({"status": "ok"})


@app.route("/api/reauth-complete", methods=["POST"])
def api_reauth_complete():
    # Plaid Link's "update mode" refreshes credentials for the existing Item in
    # place - there's no new access_token to exchange, we just clear the error.
    conn = get_db()
    state = models.get_sync_state(conn)
    if state:
        models.update_sync_progress(conn, state["item_id"], state["cursor"], None)
    return jsonify({"status": "ok"})


@app.route("/triage")
def triage_view():
    conn = get_db()
    benefits = load_benefits(BENEFITS_PATH)
    transactions = models.get_unreviewed_credits(conn)
    return render_template("triage.html", transactions=transactions, benefits=benefits)


@app.route("/triage/<transaction_id>", methods=["POST"])
def triage_label(transaction_id):
    conn = get_db()
    assigned = request.form.get("assigned_benefit_id") or None
    note = request.form.get("note", "")
    if assigned == "ignore":
        assigned = None

    txn = models.get_transaction(conn, transaction_id)
    models.label_transaction(conn, transaction_id, assigned, note)

    if assigned and txn:
        flash(
            f'Labeled as "{assigned}". Consider adding a match pattern for '
            f'"{txn["name"]}" (merchant: "{txn["merchant_name"]}") to config/benefits.yaml '
            "so similar transactions match automatically next time."
        )
    return redirect(url_for("triage_view"))


if __name__ == "__main__":
    app.run(debug=True)
