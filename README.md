# DND and Beyond

A polished 5e-compatible character, campaign, and DM table app built with Reflex.

This restart focuses on the product bar from the kickoff prompt: exact derived-stat math, local SRD rules data, a phone-friendly character sheet, and a DM view that opens directly onto "where we last left off."

## How campaigns work

1. **The DM hosts a campaign** from the dashboard. The campaign gets an invite code (e.g. `DRAGON-4271`) with a copy button on the campaign page.
2. **Players join** from the dashboard's "Join a Campaign" panel: paste the invite code, pick one of your characters from the dropdown (optional), and join. You land directly in the campaign hub.
3. **Attach or switch your character any time** from the "My Character" panel in the campaign hub. The same character can play in as many campaigns as you like.
4. **Campaign state persists**: shared notes, DM notes, the session log, and party HP are saved to the database automatically (notes save when you click away from the text box).

The Sheet page shows all of your characters — switch between them with the chips at the top.

## What is included

- Reflex app scaffold with a custom tabletop design system
- Email-based register/login flow with verification
- Local development email outbox for verification codes
- Blank-by-default user dashboards
- Dashboard showing the logged-in user's characters, campaign attachments, and DM/player campaign roles
- Character builder that creates a calculated sheet
- Character sheet with pinned AC, HP, initiative, proficiency, tabs, spells, inventory, features, and notes
- Campaign hub with session log, shared notes, roster HP/location/conditions, invite code, join flow, and dice roller
- DM view with party status board, DM notes, NPC tracker, and initiative tracker
- HP changes in the initiative tracker sync back to the party status board
- SQLite schema for users, characters, campaigns, campaign memberships, DM notes, NPCs, initiative state, and local rules tables
- SRD seed script using `dnd5eapi.co`
- Automated tests for official 5e derived-stat math
- CC-BY-4.0 SRD attribution in the app footer

## Setup

From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Seed local SRD rules data

```powershell
python scripts\seed_srd.py
```

The app should not call external rules APIs during core flows. This script pulls the SRD once and stores it locally.

## Local email verification

For local testing, registration does not send real email unless SMTP settings are configured. Verification messages are written next to the SQLite database. By default, runtime data lives outside this repo:

```text
../.dnd_and_beyond_runtime/data/dev_email_outbox.log
```

Register, open that outbox, copy the verification code, then use the Verify Email tab in the app. Later, set `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and related values from `.env.example` to send real verification email.

Do not keep the active SQLite database inside this repo while running `reflex run`. Reflex watches the project tree for source changes, and SQLite WAL/SHM writes can trigger a browser refresh loop.

## Run tests

```powershell
python -m pytest
```

## Run the app

```powershell
reflex run
```

Then open:

```text
http://localhost:3000
```

The backend defaults to `http://localhost:8101` to avoid common local conflicts
on port 8000. To use another backend port for a session:

```powershell
$env:REFLEX_BACKEND_PORT=8000
reflex run
```

## Project structure

```text
DndAndBeyond/
  assets/
    styles.css
  dnd_and_beyond/
    dnd_and_beyond.py
    data_access.py
    models.py
    rules_math.py
    state.py
  scripts/
    seed_srd.py
  tests/
    test_rules_math.py
  DECISIONS.md
  README.md
  rxconfig.py
```

## Deploying (single-container Docker)

The repo ships a production [Dockerfile](Dockerfile) based on Reflex's official
"simple-one-port" pattern: Caddy serves the compiled frontend and proxies the
websocket/backend routes on one port, with Redis inside the container for
session state. The SQLite database lives at `/data`, which must be a
**persistent volume** on your platform or all accounts/campaigns vanish on
each redeploy.

Test it locally:

```powershell
docker build -t dnd-and-beyond .
docker run -p 8080:8080 -v dnd_data:/data dnd-and-beyond
# open http://localhost:8080
```

### Database

The app runs on SQLite locally (zero setup) and on **Postgres in production**:
set `DATABASE_URL` to a Postgres connection string (e.g. from
[Neon](https://neon.tech)'s free tier) and every query runs against it. This is
required on serverless platforms like Cloud Run, whose filesystems are wiped on
every restart.

### Google Cloud Run + Neon (recommended: ~free at small scale)

1. Create a free [Neon](https://neon.tech) project and copy its connection
   string (`postgresql://...neon.tech/...?sslmode=require`).
2. Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install), run
   `gcloud auth login`, and create a Google Cloud project with billing enabled
   (friends-group usage stays inside the free tier).
3. Copy `.env.production.example` to `.env.production` and fill in the Neon
   URL and Gmail SMTP values. For Gmail, create an
   [App Password](https://myaccount.google.com/apppasswords) (requires
   2-Step Verification) — never your real password.
4. Verify the production email login:

   ```powershell
   .\.venv\Scripts\python.exe scripts\verify_smtp.py
   ```

   This should print `SMTP_OK`. If it prints `SMTP_AUTH_FAILED`, replace
   `SMTP_PASSWORD` with a Gmail App Password.
5. Verify the production database connection:

   ```powershell
   .\.venv\Scripts\python.exe scripts\verify_postgres.py
   ```

   The script creates a uniquely named throwaway account, character, and
   campaign, verifies the core read paths, then deletes only those smoke-test
   records.
6. Deploy:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\deploy_cloudrun.ps1 -ProjectId your-project-id
   ```

   Replace `your-project-id` with the Google Cloud **Project ID** shown in the
   Google Cloud Console project selector. It is usually lowercase with hyphens,
   such as `dnd-and-beyond-123456`; it is not necessarily the same as the
   project display name.

The script enables the needed Google APIs, builds the container with Cloud
Build, deploys with websocket-friendly settings (`--session-affinity`,
`--timeout 3600`), and — on the very first deploy — automatically rebuilds
once more so the app's real public URL is compiled into the frontend. Re-run
the same command any time you want to ship an update.

Without `SMTP_*` set, verification codes are written to a log file inside the
container — fine for testing, but players can't read that file, so real email
is required for public signups.

## Legal and sourcing

Rules content is intended to come from the 5.1 SRD via `dnd5eapi.co`, redistributed under CC-BY-4.0. This project does not use Wizards of the Coast logos, the official ampersand logo, or non-SRD Player's Handbook content.

## Next improvements

- Expand the character builder with point buy, species/class feature selection, equipment packs, and prepared spell management.
- Live sync between connected players (today another player's changes appear after you reopen the campaign).
- Add screenshots after the first local visual QA pass.
- Add end-to-end checks for the mobile character sheet and mobile initiative tracker.
