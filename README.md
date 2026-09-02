# WorthIt

A private dashboard for tracking recurring American Express Gold Card benefits.
WorthIt reads card transactions through Plaid and shows what has been used,
what is pending, and what is close to expiring.

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
- Sync and warning thresholds: `config/settings.yaml`

Uber usage is inferred from Uber spending. Dining, Dunkin', and Resy are
matched from their Amex statement-credit transactions.

## Test

```bash
.venv/bin/python -m pytest
```

## Privacy

WorthIt is a single-user, localhost application. Plaid tokens and transactions
are stored in a private Docker volume (or ignored `data/` files outside
Docker). The container binds only to `127.0.0.1`. Never commit `.env`, share
Plaid secrets, or expose the real-data instance to the internet.
