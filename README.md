# Amex Gold Benefit Tracker

Tracks whether you're using your Amex Gold card's recurring statement
credits each period (Uber/Uber Eats, Dining, Dunkin', Resy), via a local
Flask dashboard backed by Plaid transaction data.

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
3. From the Plaid dashboard, grab your `client_id` and `secret`.
4. Copy `.env.example` to `.env` and fill in `PLAID_CLIENT_ID`, `PLAID_SECRET`.
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
- `spend_threshold`: credit is auto-applied once you spend enough at a
  matching merchant (e.g. Uber) - no separate credit transaction to match.
- `credit_match`: Amex posts its own statement-credit transaction after you
  pay the merchant (e.g. Dunkin', Dining, Resy) - matched by description text.

**The Dining and Resy match patterns in the seed config are best guesses**
(only the Dunkin' pattern - `"Amex Dunkin Credit"` - is confirmed from real
data). After your first real statement cycle, check the "Review
Transactions" page (`/triage`) for any credit-looking transaction that
didn't get auto-matched, label it there, and update the corresponding
`match` patterns in `benefits.yaml` so it matches automatically going forward.

Resy also requires one-time manual enrollment via the Benefits section of
amex.com, and its credit can take up to 8 weeks to post - the dashboard
won't flag it "at risk" if a qualifying purchase happened recently.

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
