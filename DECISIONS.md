# Decisions

## 2026-07-07

- Restarted in a new `DndAndBeyond` folder instead of modifying the earlier `DnDCampaignCreator` attempt, so the UI and architecture can be reset cleanly.
- Chose Reflex to match the kickoff prompt and used the current documented structure: app package, `rxconfig.py`, `rx.Model` tables, and `rx.session`-compatible schema.
- Kept the visual direction premium fantasy tabletop software without copying Wizards of the Coast logos, the official ampersand, or protected D&D Beyond trade dress.
- Put exact 5e derived-stat rules in `dnd_and_beyond/rules_math.py` with tests before treating character creation as trustworthy.
- Modeled current HP, location, and active conditions on `CampaignMember`, not `Character`, because those are campaign-specific state.
- Added a seed script that pulls CC-BY-4.0 SRD data from `dnd5eapi.co` into local sqlite tables so core flows do not depend on live API calls at runtime.
- Built the first app slice with in-memory Reflex state for fast iteration, while the database schema and seeder are ready for persistent event wiring.

## 2026-07-08

- Removed seeded play data from application state. Rules data remains seedable, but user-facing characters and campaigns now start blank.
- Shifted login/register toward a real email-owned model: users register with email and password, must verify email, and then see only their own characters and campaign memberships.
- Added local development email verification through `dnd_and_beyond/data/dev_email_outbox.log`; SMTP can be enabled later with environment variables when hosting.
- Persisted characters, campaigns, campaign membership roles, and campaign attachment notes in SQLite so the dashboard can show "player" or "dm" per campaign.
- Kept hosting deployment out of scope for now; local testing remains the priority until the app reaches a finished state.

## 2026-07-10

- Replaced the prototype tabbed sheet with a traditional, responsive character sheet layout while keeping the app's burgundy and brass visual system.
- Bundled all 319 spells from the SRD 5.1-compatible 2014 catalog locally so runtime magic flows are deterministic and do not depend on an external API.
- Added class-aware spellcasting rules for full and half casters, Wizard spellbooks, prepared and known spells, Warlock Pact Magic, Bard Magical Secrets, and racial innate spells.
- Stored spell selections as a structured JSON envelope in the existing character column, with a compatibility fallback for characters created by the earlier comma-separated format.
