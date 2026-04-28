# Elevenlabs-Account

> Telegram bot that creates ElevenLabs accounts end-to-end — one tap or in bulk, with live progress, instant credential delivery, and a built-in account history.

A multi-user Telegram bot that automates the full ElevenLabs signup flow: provisions a fresh disposable mailbox, drives the signup form through an anti-detect browser, retrieves and clicks the verification email, completes the post-signin onboarding wizard, and stores both credential pairs in a database — all surfaced through a clean inline-keyboard UI.

---

## Features

- **One-tap account creation** — `/create` runs the entire pipeline (mailbox → signup → verify → onboarding → store) with live progress edits in chat.
- **Bulk creation** — make up to 20 accounts in a single command, sequential and throttled to dodge detection.
- **Multi-user with allowlist** — admin-managed user list stored in the database; everyone else is blocked at the door.
- **Live progress** — the same Telegram message updates in place: `[1/5] → [2/5] → … → ✅ Account ready`.
- **Tap-to-copy credentials** — every email and password renders as inline `<code>` so a single tap copies the value.
- **Account history** — paginated `My Accounts` list, tap any row to re-show its full credentials.
- **Stats** — today / all-time counts with success/failure breakdown; admin sees a global view.
- **Export** — download all your accounts as CSV or paste-ready TXT (`email:password` per line).
- **Two browser backends** — anti-detect mode for production, plain headless Chromium for testing.

---

## How it works

Each `/create` runs through five steps. The Telegram message edits in place at every transition so the user sees what's happening.

```
[1/5] Generating mailbox at PinMX…           ─── disposable mailbox provisioned
[2/5] Submitting elevenlabs.io signup…       ─── email + password submitted
[3/5] Waiting for verification email…        ─── inbox polled until verify URL arrives
[4/5] Verifying & signing in…                ─── verify link → modal → sign-in form
[5/5] Completing onboarding…                 ─── name → agree → skip × 3 → done
       ↓
✅ Account ready
```

The success message returns both credential pairs (mailbox + ElevenLabs) in monospace so each value is one tap to copy.

---

## Tech stack

- **Python 3.11+** — async-first
- **python-telegram-bot v21** — long-polling, inline keyboards, message editing
- **Playwright (Chromium)** — drives the ElevenLabs signup form
- **Kameleo** — anti-detect browser launches (fresh fingerprint per signup); falls back to plain Playwright
- **PinMX** — disposable mailbox API (Growth tier required for `/v1/mail/create`)
- **Supabase** — Postgres-backed storage for accounts and the allowlist
- **httpx** — async HTTP for PinMX
- **loguru** — structured logging

---

## Setup

### 1. Prerequisites

- Python 3.11 or newer
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Your numeric Telegram user ID from [@userinfobot](https://t.me/userinfobot)
- A Supabase project ([supabase.com](https://supabase.com)) — free tier is plenty
- A PinMX **Growth** subscription ($5/mo) — Foundation tier does not include API access
- *(Optional but recommended)* A Kameleo subscription with the local CLI running on `localhost:5050`

### 2. Clone and install

```bash
git clone https://github.com/thedepegger/Elevenlabs-Account.git
cd Elevenlabs-Account
pip install -e .
playwright install chromium
```

### 3. Create the database tables

In your Supabase project's SQL editor, paste and run the contents of [`scripts/init_db.sql`](scripts/init_db.sql). Two tables are created: `accounts` and `allowed_users`.

### 4. Configure environment

```bash
cp .env.example .env
```

Then fill in `.env` — see the [Configuration](#configuration) section below.

### 5. Run

```bash
python -m src
```

You should see:

```
Bootstrap admin <your_id> ensured
PinMX self-check OK (Growth tier active)
Kameleo self-check OK at http://localhost:5050
Bot started, admin bootstrapped — ready to accept messages
```

DM the bot `/start` and you'll see the main menu.

---

## Configuration

All settings live in `.env`. See `.env.example` for the template.

| Variable | Required | What it is |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | From @BotFather |
| `ADMIN_TELEGRAM_ID` | yes | Your numeric Telegram user id (bootstrap admin) |
| `PINMX_TOKEN` | yes | Your PinMX API token (Growth tier required) |
| `PINMX_DOMAINS` | no | Comma-separated mailbox domains. Default: `pinmx.net,pingmx.com` |
| `SUPABASE_URL` | yes | `https://xxxxx.supabase.co` from project settings |
| `SUPABASE_SERVICE_KEY` | yes | The `service_role` key (NOT the `anon` key) |
| `BROWSER_MODE` | no | `kameleo` (default) or `playwright` |
| `KAMELEO_BASE_URL` | no | Default `http://localhost:5050` |
| `KAMELEO_DEVICE_TYPE` | no | Default `desktop` |
| `KAMELEO_BROWSER_PRODUCT` | no | Default `chrome` |
| `KAMELEO_OS_FAMILY` | no | Default `windows` |
| `HEADLESS` | no | Default `true` (only used with `BROWSER_MODE=playwright`) |
| `VERIFY_TIMEOUT_SECONDS` | no | Default `120` (mailbox polling timeout) |
| `BULK_THROTTLE_SECONDS` | no | Default `45` (delay between bulk attempts) |
| `BULK_MAX` | no | Default `20` (cap per `/bulk N`) |
| `LIST_PAGE_SIZE` | no | Default `10` |
| `LOG_LEVEL` | no | Default `INFO` |

The `SUPABASE_ACCESS_TOKEN` and `SUPABASE_PROJECT_REF` fields in `.env.example` are only needed if you also want to wire up the [Supabase MCP server](https://github.com/supabase-community/supabase-mcp) for managing your project from Claude Code or similar agents — they aren't read by the bot itself.

---

## Bot commands

| Command | Inline button | Who | What |
|---|---|---|---|
| `/start`, `/menu`, `/help` | — | allowed | Main menu / help text |
| `/create` | 🤖 Create Account | user/admin | One ElevenLabs account end-to-end |
| `/bulk N` | 📦 Bulk Create | user/admin | N accounts (1–20), sequential, throttled |
| `/list` | 📋 My Accounts | user (own) / admin (all) | Paginated history |
| `/stats` | 📊 Stats | allowed | Today / all-time counts |
| `/export` | 📤 Export | user (own) / admin (all) | CSV or TXT file |
| `/add_user <id> [user\|admin]` | 👥 → Add | admin only | Allow a user |
| `/remove_user <id>` | 👥 → Remove | admin only | Revoke access |
| `/list_users` | 👥 Manage Users | admin only | Show the allowlist |

---

## Success-message format

After a successful `/create`, the message edits to:

```
✅ Account ready

📬 Mailbox login
https://mail-client.pinmx.com
Email: kx9mp2tq4z@pinmx.net
Pass:  Pq7$Rt2vNkLm@9Yz

🎙 ElevenLabs
Email: kx9mp2tq4z@pinmx.net
Pass:  Xm9!2vRq8KpL$nW3

[Create another] [Menu]
```

The email shows under each platform on purpose so each block reads as a complete login. Every credential renders as monospace `<code>` for one-tap copy.

---

## Project structure

```
.
├── .env.example           # config template
├── Dockerfile             # playwright base image; defaults to BROWSER_MODE=playwright
├── pyproject.toml
├── scripts/
│   └── init_db.sql        # Supabase schema (accounts, allowed_users)
└── src/
    ├── __main__.py        # `python -m src` entry
    ├── bot.py             # Application wiring + lifecycle
    ├── config.py          # Settings dataclass loaded from .env
    ├── auth.py            # @require_allowed / @require_admin decorators
    ├── pinmx.py           # PinMX API client (create_mailbox, list_messages)
    ├── kameleo.py         # Kameleo SDK wrapper (per-signup profile lifecycle)
    ├── elevenlabs.py      # Playwright signup + verify + onboarding
    ├── workflow.py        # The 5-step orchestrator
    ├── supabase_client.py # Repo for accounts + allowlist
    ├── generators.py      # Random username/password/USA-male-first-name
    ├── format.py          # MarkdownV2 escaping + tap-to-copy formatting
    ├── menu.py            # All inline keyboard layouts
    ├── exporter.py        # CSV + TXT serializers
    └── handlers/          # One file per command/button
        ├── start.py
        ├── create.py
        ├── bulk.py
        ├── list.py
        ├── stats.py
        ├── export.py
        └── admin.py
```

---

## Notes

- **Disposable email blocklists** — PinMX domains (`pinmx.net`, `pingmx.com`) are publicly listed as disposable. The workflow rotates domains automatically (up to 3 attempts) when ElevenLabs rejects an email; if all PinMX domains end up blocked, swap to a different mailbox provider.
- **Anti-bot detection** — Kameleo's fresh-fingerprint-per-signup is the main defense. The bot does not currently use proxies; if detection becomes an issue at scale, route Kameleo through residential proxies.
- **Selectors** — every selector lives in `src/elevenlabs.py` so a single edit fixes any markup drift on the ElevenLabs side.
- **ElevenLabs Terms of Service** — bulk-creating accounts violates ElevenLabs' ToS. Accounts may be banned post-creation. Use responsibly. This project is provided as-is for educational purposes.

---

## License

Personal / educational use. No warranty.
