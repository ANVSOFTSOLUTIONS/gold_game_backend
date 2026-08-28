# NineBox API

FastAPI backend for the NineBox number-guessing game. Implements the core
gameplay loop from the frontend's mock store (`useGameStore.ts`) for real:
phone/OTP auth, wallet (balance/add/withdraw/transactions), and a
server-authoritative game round (place bet, random draw, payout).

Referral, rewards/points redemption, leaderboard, KYC, support and
notifications are **not** included yet — this covers auth + wallet + game
only. Ask for the rest whenever you're ready to add them.

## Stack

- FastAPI + Pydantic v2
- SQLAlchemy 2.0 (sync) + PostgreSQL
- JWT auth (python-jose), OTP hashed with bcrypt (passlib)
- A background `asyncio` task runs the shared round clock (draw + payout)
  automatically every `ROUND_LENGTH_SECONDS`

## Setup

1. Start Postgres (or point `DATABASE_URL` at one you already have):
   ```
   docker compose up -d
   ```
2. Create a virtualenv and install dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Copy the env template and adjust as needed:
   ```
   copy .env.example .env
   ```
4. Run the API:
   ```
   uvicorn app.main:app --reload
   ```
5. Open the interactive docs at http://127.0.0.1:8000/docs — tables are
   created automatically on startup, no migration step needed yet.

## Auth flow

There's no password — it's phone + OTP, matching the frontend's UI:

1. `POST /auth/signup` `{full_name, mobile}` → creates the user + wallet,
   generates an OTP.
2. `POST /auth/verify-otp` `{mobile, code}` → returns a JWT `access_token`.
3. For returning users: `POST /auth/request-otp` `{mobile}` then
   `POST /auth/verify-otp` the same way.

**No SMS provider is wired up.** While `DEBUG=true`, the OTP is returned in
the response as `dev_otp` so you can test end-to-end locally. Before any
real deployment: set `DEBUG=false` and send the code via a real provider
(Twilio, MSG91, etc.) inside `_issue_otp()` in `app/routers/auth.py`.

Send the JWT on every authenticated request:
```
Authorization: Bearer <access_token>
```

## Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/signup` | – | create account, sends OTP |
| POST | `/auth/request-otp` | – | resend OTP for login |
| POST | `/auth/verify-otp` | – | returns JWT |
| GET | `/wallet` | ✅ | balance / playable / withdrawable / points / streak |
| POST | `/wallet/add` | ✅ | mock top-up (no real payment gateway yet) |
| POST | `/wallet/withdraw` | ✅ | capped at `withdrawable` |
| GET | `/wallet/transactions` | ✅ | paginated, newest first |
| GET | `/game/current-round` | – | shared round id, seconds left, drawn number if closed |
| POST | `/game/bets` | ✅ | `{picks: [1,9], stake: 50}` — costs `stake × len(picks)` |
| GET | `/game/last-draws` | – | last 6 drawn numbers |

## Game logic (matches the frontend exactly)

- One shared round runs at a time (not per-user) — `ROUND_LENGTH_SECONDS`
  long, closed automatically by the background loop.
- Placing a bet costs `stake × number_of_picks`.
- If the drawn number is *any* of your picks, that bet wins `stake × 9`
  (a single 9x payout per bet, not per matching pick — same as the
  original `draw()` logic in `useGameStore.ts`).
- Points: `+10` for playing, `+100` bonus on a win. Streak increments on a
  win, resets to 0 on a loss.

## Not done yet (flagged on purpose)

- No real payment gateway — `/wallet/add` and `/wallet/withdraw` move
  numbers around directly, same as the current frontend mock.
- No real SMS provider for OTP delivery.
- No Alembic migrations — schema is created via `Base.metadata.create_all`
  on startup. Fine for now, worth adding before this touches real data.
- Referral / rewards / leaderboard / KYC / support / notifications
  endpoints aren't built — say the word and I'll add them the same way.
