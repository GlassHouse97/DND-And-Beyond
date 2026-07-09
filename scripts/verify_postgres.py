"""Smoke-test the production Postgres data layer.

This script loads DATABASE_URL from .env.production, initializes the schema,
creates a uniquely named throwaway user/character/campaign, verifies the core
read paths, and cleans up only those throwaway records.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Copy .env.production.example and fill it in first.")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the production Postgres connection safely.")
    parser.add_argument(
        "--env-file",
        default=".env.production",
        help="Path to the production env file. Defaults to .env.production.",
    )
    args = parser.parse_args()

    try:
        load_env_file(Path(args.env_file))
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url.startswith(("postgres://", "postgresql://")):
        print("DATABASE_URL must be a Postgres connection string.", file=sys.stderr)
        return 1

    # Import after DATABASE_URL is loaded so data_access selects Postgres mode.
    from dnd_and_beyond import data_access as data

    suffix = uuid.uuid4().hex[:12]
    email = f"codex-smoke-{suffix}@example.invalid"
    token = f"verify-{suffix}"
    user_id: int | None = None
    character_id: int | None = None
    campaign_id: int | None = None

    try:
        data.initialize_database()
        created, reason = data.create_user(email, "hash-smoke", "Codex Smoke Test", token)
        if not created:
            raise RuntimeError(f"Could not create smoke-test user: {reason}")
        if not data.verify_user_email(email, token):
            raise RuntimeError("Could not verify smoke-test user.")

        user = data.get_user_by_email(email)
        if user is None:
            raise RuntimeError("Smoke-test user was not readable after creation.")
        user_id = int(user["id"])

        character_id = data.create_character(
            user_id,
            {
                "name": f"Smoke Hero {suffix}",
                "ancestry": "Human",
                "character_class": "Fighter",
                "background": "Soldier",
                "level": 1,
                "str": 15,
                "dex": 14,
                "con": 13,
                "int": 12,
                "wis": 10,
                "cha": 8,
                "armor": "chain mail",
                "shield": True,
                "skills": "Athletics",
                "saves": "Strength, Constitution",
                "notes": "temporary production smoke test",
            },
        )
        campaign_id = data.create_campaign(user_id, f"Smoke Campaign {suffix}", "temporary", f"SMOKE-{suffix[:6].upper()}")

        characters = data.list_user_characters(user_id)
        campaigns = data.list_user_campaigns(user_id)
        if not any(int(character["id"]) == character_id for character in characters):
            raise RuntimeError("Smoke-test character was not returned by list_user_characters.")
        if not any(int(campaign["id"]) == campaign_id and campaign["role"] == "dm" for campaign in campaigns):
            raise RuntimeError("Smoke-test campaign was not returned by list_user_campaigns.")

        print("POSTGRES_SMOKE_OK")
        return 0
    finally:
        if user_id is not None or campaign_id is not None or character_id is not None:
            with data.connect() as conn:
                if campaign_id is not None:
                    conn.execute(data._q("DELETE FROM initiative_combatants WHERE campaign_id = ?"), (campaign_id,))
                    conn.execute(data._q("DELETE FROM npcs WHERE campaign_id = ?"), (campaign_id,))
                    conn.execute(data._q("DELETE FROM dm_notes WHERE campaign_id = ?"), (campaign_id,))
                    conn.execute(data._q("DELETE FROM campaign_members WHERE campaign_id = ?"), (campaign_id,))
                    conn.execute(data._q("DELETE FROM campaigns WHERE id = ?"), (campaign_id,))
                if character_id is not None:
                    conn.execute(data._q("DELETE FROM campaign_members WHERE character_id = ?"), (character_id,))
                    conn.execute(data._q("DELETE FROM characters WHERE id = ?"), (character_id,))
                if user_id is not None:
                    conn.execute(data._q("DELETE FROM campaign_members WHERE user_id = ?"), (user_id,))
                    conn.execute(data._q("DELETE FROM users WHERE id = ?"), (user_id,))
                conn.commit()


if __name__ == "__main__":
    raise SystemExit(main())
