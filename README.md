# Amex Gold Benefit Tracker

Tracks whether you're using your Amex Gold card's recurring benefits each
period (Uber/Uber Eats, Dining, Dunkin', Resy), via a local Flask dashboard
backed by Plaid transaction data.

## Setup

### 1. Install dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Get Plaid API access

1. Sign up for a [Plaid developer account](https://dashboard.plaid.com/signup).
2. Request **Trial plan** access (free, supports up to 10 real Production
   Items with live data - no full Production approval needed for personal use).
3. From the Plaid dashboard, grab your `client_id`, Sandbox secret, and
   Production secret (when available).
4. Copy `.env.example` to `.env` and fill in `PLAID_CLIENT_ID`,
   `PLAID_SECRET_SANDBOX`, and `PLAID_SECRET_PROD`.
   Leave `PLAID_ENV=sandbox` for initial testing; switch to `production` once
   you're ready to link your real Amex card.

`.env` is gitignored - never commit it.

### 3. Run the app

```bash
.venv/bin/python app.py
```

Visit http://127.0.0.1:5000. On first run you'll see a "Link your Amex card"
prompt - click through Plaid Link to connect it.

### 4. (Optional) Keep data fresh with cron

The dashboard syncs itself when data is stale (see `sync_stale_minutes` in
`config/settings.yaml`), so cron is not required. If you want the cache
warm even when you're not looking at the dashboard:

```
*/30 * * * * cd /home/denys/worthit && .venv/bin/python scripts/cron_sync.py >> data/cron_sync.log 2>&1
```

## Demo mode

There's a `DEMO_MODE` flag that renders the dashboard with mock, relative-dated
transaction data instead of touching the database or Plaid at all - useful for
showing off the project (e.g. to recruiters) without exposing your real
financial data. In demo mode:
- The dashboard renders from in-memory mock data (`worthit/demo_data.py`),
  showcasing one benefit in each state (complete/partial/pending).
- A banner appears on every page noting it's a demo and linking back here.
- `/link`, `/reauth`, and all `/api/*` Plaid routes are hard-disabled (return
  403 or redirect) - even if real Plaid keys are present in the environment,
  demo mode never calls them.
- Nothing is written to disk; every visitor sees the same fresh mock state.

Run it locally with:

```bash
DEMO_MODE=true .venv/bin/python app.py
```

This is meant to be the version deployed publicly (e.g. Render/Fly.io/Railway),
while your personal instance with real Plaid credentials stays local-only,
started with `DEMO_MODE` unset (or `false`) as in the steps above.

### Public-repository and deployment safety

- `.env`, SQLite databases, and `data/` are ignored by Git. Never force-add
  them or paste Plaid secrets into issues, commits, screenshots, or logs.
- A public deployment must set `DEMO_MODE=true`. Demo routes do not open the
  financial database and return 403 for every Plaid API action.
- Keep the real-data instance bound to localhost. It is a single-user tool and
  intentionally has no internet-facing authentication layer.
- Keep `FLASK_DEBUG=false`, especially for any publicly reachable process. The
  interactive debugger can execute code and must never be exposed.
- Plaid access tokens are stored in the ignored local SQLite database. Protect
  that file and do not sync or publish the `data/` directory.
- Sandbox and Production use separate ignored databases
  (`data/worthit-sandbox.db` and `data/worthit-production.db`) so a test access
  token can never be sent to the Production API after changing environments.

## Known Amex + Plaid quirk

Amex connections through Plaid are known to require frequent
re-authentication ("perpetual MFA"). This is expected, not a bug - when it
happens, the dashboard shows a "Reconnect" banner; click through it to
restore the connection without creating a duplicate.

## Editing benefit definitions

`config/benefits.yaml` defines each tracked benefit - amount, period,
detection mode, and the merchant/description text patterns used to
recognize matching transactions. No code changes needed to adjust these.

Two detection modes:
- `spend_threshold`: matching spend is used as evidence that a benefit was
  used (currently Uber, based on this cardholder's usage pattern). Uber Cash
  lives in the Uber account and does not appear as an Amex statement credit.
- `credit_match`: Amex posts its own statement-credit transaction after you
  pay the merchant (e.g. Dunkin', Dining, Resy) - matched by description text.

The Dining, Dunkin', and Resy statement-credit descriptions are confirmed
from real card data. If Amex changes those descriptions, update the
corresponding `match` patterns in `benefits.yaml`.

Dining, Dunkin', and Resy require enrollment via the Benefits section of
amex.com. Statement credits can take time to post. Resy can take up to 8
weeks, so the dashboard won't flag it "at risk" if it recognizes a recent
qualifying purchase. This hint is best-effort because the charge may show the
restaurant's name without mentioning Resy.

## Testing

```bash
.venv/bin/python -m pytest
```

`test_periods.py`, `test_matcher.py`, `test_status.py`, and
`test_sync_cursor.py` run fully offline (no network, no real Plaid
credentials needed). To verify the real Plaid wiring end-to-end before
linking your actual Amex card, use Plaid's Sandbox environment
(`PLAID_ENV=sandbox`) with a test institution and Plaid's documented sandbox
credentials, then use `POST /sandbox/item/reset_login` (via Plaid's API,
outside this app) to simulate the `ITEM_LOGIN_REQUIRED` reconnect flow.
