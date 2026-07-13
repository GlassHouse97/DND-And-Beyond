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
- Traditional character sheet with identity, ability cards, saves, skills, combat stats, attacks, features, equipment, and spellcasting
- Campaign hub with session log, shared notes, roster HP/location/conditions, invite code, join flow, and dice roller
- DM view with party status board, DM notes, NPC tracker, and initiative tracker
- HP changes in the initiative tracker sync back to the party status board
- SQLite schema for users, characters, campaigns, campaign memberships, DM notes, NPCs, initiative state, and local rules tables
- Complete bundled SRD 5.1 spell catalog: all 319 spells, levels 0-9, components, casting details, descriptions, scaling, and class access
- Class-aware magic rules for prepared, known, spellbook, Pact Magic, Magical Secrets, and ancestry innate spells
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

## Refresh the bundled spell catalog

The application ships with the complete 319-spell SRD 5.1 catalog at
`dnd_and_beyond/data/srd_spells_2014.json`, so character creation and the
character sheet do not depend on an external rules API. To refresh the source
data intentionally:

```powershell
python scripts\build_srd_spell_catalog.py
```

The builder enforces class access, level limits, cantrip limits, Wizard
spellbook/prepared lists, and the appropriate known/prepared progression for
each supported SRD class. Racial innate spells are stored separately from
class spell selections.

## Local email verification

For local testing, registration does not send real email unless SMTP settings are configured. Verification messages are written next to the SQLite database. By default, runtime data lives in a Git-ignored and watcher-excluded project directory:

```text
./.workspace_data/runtime/data/dev_email_outbox.log
```

Register, open that outbox, copy the verification code, then use the Verify Email tab in the app. Later, set `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and related values from `.env.example` to send real verification email.

Do not keep the active SQLite database elsewhere inside the watched source tree
while running `reflex run`. SQLite WAL/SHM writes can trigger a browser refresh
loop unless the containing directory is explicitly excluded.

Local Reflex build output, state snapshots, npm cache files, and SQLite runtime
data are consolidated under `./.workspace_data/`. The folder is generated
locally, ignored by Git and Docker, and excluded from Reflex hot reload. It is
not part of the Cloud Run deployment.

## Run tests

```powershell
python -m pytest
```

## Run the app

```powershell
reflex run
```

## Reset User Data

To permanently remove every account, character, campaign, and other
user-created record while retaining the SRD rules catalog and database schema:

```powershell
python scripts\purge_app_data.py --dry-run
python scripts\purge_app_data.py --confirm
```

For the hosted Postgres database, use the gitignored production configuration:

```powershell
python scripts\purge_app_data.py --dry-run --production-env-file .env.production
python scripts\purge_app_data.py --confirm --production-env-file .env.production
```

The purge is permanent. The production command should only be run when the
whole group is intentionally starting over.

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

### Cloud-owned secrets and automatic deployment

Production credentials are kept out of Git. Store the Neon connection string
and Gmail App Password in a password manager as a recovery copy, then migrate
the local deployment values into Google Secret Manager once:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_cloud_secrets.ps1 -ProjectId your-project-id
```

This creates a dedicated Cloud Run runtime identity. It can read only the
specific Secret Manager values the app needs; the local `.env.production` file
is no longer used for routine deployments.

To connect GitHub and deploy every push to `main`, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_github_build_trigger.ps1 -ProjectId your-project-id
```

The first run prints a GitHub authorization URL. Authorize the Cloud Build
GitHub App for `GlassHouse97/DND-And-Beyond`, then run the same command again
to create the trigger. From that point forward, Cloud Build uses
`cloudbuild.github.yaml` to build and deploy the app from `main` automatically.

`scripts\deploy_cloudrun.ps1` remains available for a manual deployment, but
it reads only Secret Manager references after the migration.

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
