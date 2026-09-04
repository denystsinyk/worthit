# WorthIt

A private dashboard for tracking recurring American Express Gold Card benefits.
WorthIt reads card transactions through Plaid and shows what has been used,
what is pending, what is close to expiring, and how much card value you have
captured over time.

Tracked benefits:

- $10 monthly Uber Cash
- $10 monthly Dining Credit
- $7 monthly Dunkin' Credit
- $50 semiannual Resy Credit

## Quick start

Requirements: Docker and your own [Plaid developer account](https://dashboard.plaid.com/signup).

```bash
git clone https://github.com/denystsinyk/worthit.git
cd worthit
cp .env.example .env
```

Add your Plaid keys to `.env`. Start with `PLAID_ENV=sandbox`:

```dotenv
PLAID_CLIENT_ID=your_client_id
PLAID_SECRET_SANDBOX=your_sandbox_secret
PLAID_SECRET_PROD=your_production_secret
PLAID_ENV=sandbox
FLASK_SECRET_KEY=your_random_secret
DEMO_MODE=false
```

Then run:

```bash
docker compose up --build
```

Docker Compose runs a companion sync process every 30 minutes so dashboard
requests remain fast. Set `SYNC_INTERVAL_SECONDS` in `.env` to change the
interval. The **Refresh now** button is available for an immediate update.

For event-driven updates on a publicly reachable deployment, configure
`PLAID_WEBHOOK_SECRET` and set `PLAID_WEBHOOK_URL` to the public HTTPS URL
`https://your-host/api/plaid-webhook/<the-same-secret>` before linking. WorthIt
handles Plaid's `SYNC_UPDATES_AVAILABLE` event and ignores unrelated events.

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Once Sandbox works,
change `PLAID_ENV` to `production` and restart with `docker compose up -d`.
Each installation must use its own Plaid credentials.

## Demo mode

Demo mode uses in-memory sample data and disables every Plaid action. Use it
for any public deployment:

Set `DEMO_MODE=true` in `.env`, then run Docker Compose normally.

## Develop without Docker

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python app.py
```

## Configuration

- Benefit amounts and matching rules: `config/benefits.yaml`
- Annual fee, Plaid history, sync, and warning settings: `config/settings.yaml`

Uber usage is inferred from Uber spending. Dining, Dunkin', and Resy are
matched from their Amex statement-credit transactions.

New connections request up to two years of Plaid history. Plaid cannot expand
an existing connection's original history window; use **Analytics → Relink for
more history** once if an older installation only shows 90 days. This removes
the current local cache before reconnecting.

## Test

```bash
.venv/bin/python -m pytest
```

## Privacy

WorthIt is a single-user, localhost application. Plaid tokens and transactions
are stored in a private Docker volume (or ignored `data/` files outside
Docker). The container binds only to `127.0.0.1`. Never commit `.env`, share
Plaid secrets, or expose the real-data instance to the internet.
