# Setup Confirmation Trading Dashboard

TradingView detects setups → sends a webhook → an LLM checks the setup against
your written rules → you watch it happen on a live dashboard, with an
Approve/Reject button if you want the final say.

Paper trading only. Nothing places a real trade unless you deliberately flip
`EXECUTION_ENABLED=true`, and even then Phase 6 execution logic is a stub —
see `backend/execution/paper.py`.

## What's built

| Phase | Status |
|---|---|
| 1 — Pine Script indicator + alert payload | ✅ Done (`pine/setup_indicator.pine`) |
| 2 — Webhook receiver + LLM confirmation | ✅ Done |
| 3 — Web dashboard + Railway deploy | ✅ Done |
| 4 — Logging/persistence + backtesting | ✅ Done |
| 5 — Telegram/email push (optional) | Stub only — not wired in |
| 6 — Execution layer (optional, gated) | Stub only — not implemented |

## Local setup

1. **Python 3.11+**, then:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in real values (see table below).
3. Run it:
   ```bash
   uvicorn backend.main:app --reload
   ```
4. Visit `http://localhost:8000/login`, enter the email you set as
   `AUTH_ALLOWED_EMAIL`. In dev (no `EMAIL_PROVIDER_API_KEY` set), the
   sign-in link is printed to your terminal logs instead of emailed —
   copy it into your browser.
5. Run tests:
   ```bash
   pytest
   ```

## Environment variables

All in `.env.example` with comments. The ones you must set before anything
works:

- `WEBHOOK_SHARED_SECRET` — long random string; TradingView must send this
  back on every alert (see "Webhook auth note" below).
- `GEMINI_API_KEY` — for the LLM confirmation layer (free tier, get it at aistudio.google.com).
- `AUTH_SECRET_KEY`, `AUTH_ALLOWED_EMAIL` — your login.
- `DATABASE_URL` — Postgres in production; SQLite is fine for local dev.

## Webhook auth note (important)

TradingView's free/basic alert webhooks send a raw JSON body but don't
always let you attach a custom header. Two options:

1. **If your TradingView plan supports custom webhook headers**: set
   `X-Webhook-Secret` to match `WEBHOOK_SHARED_SECRET`. This is what
   `backend/webhook/security.py` checks by default.
2. **If it doesn't**: embed the secret as a field inside the alert JSON
   itself (Pine Script's `alert()` message is just a string, so you can
   append it), and switch `verify_shared_secret` to compare a field in the
   body instead of a header. I keep the schema/security module separate so
   this swap is a small, contained change — say the word if you hit this
   and want it flipped.

Either way: never leave the endpoint unauthenticated.

## Deploying to Railway

1. Push this repo to GitHub, then in Railway: **New Project → Deploy from
   GitHub repo**.
2. **Add a Postgres plugin** to the project — Railway sets `DATABASE_URL`
   automatically.
3. Under the web service's **Variables** tab, add everything from
   `.env.example` except `DATABASE_URL` (Postgres plugin sets that) and
   `ENV` (set it to `production`).
4. Railway picks up `railway.json` automatically for the start command.
5. Once deployed, set `APP_BASE_URL` to your Railway-assigned domain (needed
   so magic-link emails point to the right place), then redeploy.
6. Point your TradingView alert's webhook URL at
   `https://<your-app>.up.railway.app/webhook/tradingview`.

**Railway hobby-tier note**: the free/hobby tier can sleep an idle service
and has DB size/connection caps. If your alert volume is low, a cold start
of a few seconds before the first webhook of the day is processed is the
main thing to expect — not a correctness problem, just a delay. Upgrade the
plan if that's ever unacceptable for a live signal.

## Paper vs. live mode

- **Paper (default)**: `EXECUTION_ENABLED=false`. Signals are confirmed and
  shown on the dashboard; nothing is simulated or executed beyond that.
- **Live**: not implemented yet. `backend/execution/paper.py` and
  `backend/execution/live.py` are intentionally stubs — building them
  requires deciding your broker/exchange, contract specs, and position
  sizing rules first, which the original brief said not to assume. Bring
  those details when you're ready for Phase 6.

## Backtesting the LLM confirmation layer

Before trusting a rules-config change or model swap live:

```bash
python -m backtest.run_backtest --source db --limit 200
```

Replays the last 200 logged signals through the *current* confirmation
logic and rules config (without touching live dashboard data), and prints a
confirm/reject/error summary. If your historical signals have known trade
outcomes, supply them via `--source file --path historical_signals.json`
with a `known_outcome_r` field per case to also get expectancy and win rate.

## Editing your methodology

Everything in `config/rules_config.yaml` is what the LLM sees. Change
thresholds, add an instrument, tweak checklist wording — no code changes,
no redeploy of logic (just restart the service to reload the file).

## Project structure

```
trading-bot/
├── pine/setup_indicator.pine       # Phase 1: TradingView indicator + alert
├── backend/
│   ├── main.py                     # FastAPI app entrypoint
│   ├── config.py                   # env var settings
│   ├── auth/                       # email magic-link login + sessions
│   ├── webhook/                    # receive, validate, dedupe, authenticate
│   ├── confirmation/                # LLM prompt, client, rules loader
│   ├── dashboard/                  # REST API, WebSocket broadcast, overrides
│   ├── db/                         # SQLAlchemy models + session
│   ├── execution/                  # Phase 6 stub, gated off
│   └── notify/                     # Phase 5 stub (Telegram), not wired in
├── frontend/                       # single-file React dashboard (no build step)
├── config/rules_config.yaml        # your editable methodology
├── tests/                          # webhook + confirmation unit tests
├── backtest/run_backtest.py        # replay historical signals
├── railway.json / .env.example / .gitignore
```

## Security checklist (already implemented)

- Webhook requires a shared secret (fail-closed if unconfigured)
- Every payload validated against a strict schema before touching any logic
- LLM prompt only ever receives structured, pre-validated data — no raw
  free-text injection surface
- Dashboard requires a login session on every route; no public data leak
- Secrets only via env vars; redacted from all logs automatically
- Rate limiting on both the webhook and the LLM confirmation call
- Every signal, verdict, login, and manual override is timestamped and
  written to `audit_log`
