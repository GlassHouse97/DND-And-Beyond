"""Persistence helpers: SQLite for local development, Postgres in production.

When DATABASE_URL is set (e.g. a Neon connection string on Cloud Run), all
functions run against Postgres via a shared connection pool. Without it, the
app uses a local SQLite file — zero setup for development and tests.

Queries are written once with "?" placeholders and translated for Postgres.
"""

from __future__ import annotations

import os
import secrets
import shutil
import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

if IS_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    _INTEGRITY_ERRORS: tuple[type[Exception], ...] = (sqlite3.IntegrityError, psycopg.errors.UniqueViolation)
else:
    _INTEGRITY_ERRORS = (sqlite3.IntegrityError,)


def _data_dir() -> Path:
    """Legacy repo-local data directory used only for one-time migration."""
    override = os.getenv("DND_DATA_DIR", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data"


def _external_data_dir() -> Path:
    """Runtime data outside the repo so Reflex hot reload ignores DB writes."""
    override = os.getenv("DND_DATA_DIR", "").strip()
    if override:
        return Path(override)
    project_root = Path(__file__).resolve().parent.parent
    return project_root.parent / ".dnd_and_beyond_runtime" / "data"


DEFAULT_DB_PATH = _external_data_dir() / "dnd_and_beyond.db"
DB_PATH = DEFAULT_DB_PATH
LEGACY_DATA_DIR = _data_dir()

# current_hp uses -1 as "not initialized yet" so a real 0 HP (down/dying) is
# distinguishable from a member whose HP was never set.
HP_UNSET = -1


_SQLITE_ID_COLUMN = "id INTEGER PRIMARY KEY AUTOINCREMENT"
_POSTGRES_ID_COLUMN = "id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY"

# users.created_at stays TEXT in both dialects; Postgres needs an explicit
# cast because it will not implicitly assign a timestamp to a text column.
_SQLITE_CREATED_AT = "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
_POSTGRES_CREATED_AT = "created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)"


SCHEMA_TEMPLATE = """
CREATE TABLE IF NOT EXISTS users (
    {id_column},
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    email_verified INTEGER NOT NULL DEFAULT 0,
    verification_token TEXT,
    {created_at_column}
);

CREATE TABLE IF NOT EXISTS characters (
    {id_column},
    owner_user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    ancestry TEXT NOT NULL,
    character_class TEXT NOT NULL,
    background TEXT NOT NULL,
    level INTEGER NOT NULL,
    strength INTEGER NOT NULL,
    dexterity INTEGER NOT NULL,
    constitution INTEGER NOT NULL,
    intelligence INTEGER NOT NULL,
    wisdom INTEGER NOT NULL,
    charisma INTEGER NOT NULL,
    armor_name TEXT NOT NULL DEFAULT 'none',
    has_shield INTEGER NOT NULL DEFAULT 0,
    skill_proficiencies TEXT NOT NULL DEFAULT '',
    save_proficiencies TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS campaigns (
    {id_column},
    host_user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    invite_code TEXT NOT NULL UNIQUE,
    next_session TEXT NOT NULL DEFAULT '',
    session_log TEXT NOT NULL DEFAULT '',
    shared_notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS campaign_members (
    {id_column},
    campaign_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    character_id INTEGER,
    role TEXT NOT NULL DEFAULT 'player',
    current_hp INTEGER NOT NULL DEFAULT -1,
    location TEXT NOT NULL DEFAULT 'Camp',
    active_conditions TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS dm_notes (
    {id_column},
    campaign_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS npcs (
    {id_column},
    campaign_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    armor_class INTEGER NOT NULL,
    current_hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL,
    key_stats TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS initiative_combatants (
    {id_column},
    campaign_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_id INTEGER,
    name TEXT NOT NULL,
    armor_class INTEGER NOT NULL,
    current_hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL,
    initiative INTEGER NOT NULL,
    turn_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rules_races (
    {id_column},
    "index" TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rules_classes (
    {id_column},
    "index" TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    hit_die INTEGER NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rules_backgrounds (
    {id_column},
    "index" TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rules_spells (
    {id_column},
    "index" TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    level INTEGER NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rules_equipment (
    {id_column},
    "index" TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    equipment_category TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rules_conditions (
    {id_column},
    "index" TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_characters_owner ON characters (owner_user_id);
CREATE INDEX IF NOT EXISTS idx_members_campaign ON campaign_members (campaign_id);
CREATE INDEX IF NOT EXISTS idx_members_user ON campaign_members (user_id);
CREATE INDEX IF NOT EXISTS idx_members_character ON campaign_members (character_id);
CREATE INDEX IF NOT EXISTS idx_npcs_campaign ON npcs (campaign_id);
CREATE INDEX IF NOT EXISTS idx_dm_notes_campaign ON dm_notes (campaign_id);
"""

SCHEMA_SQL = SCHEMA_TEMPLATE.format(
    id_column=_SQLITE_ID_COLUMN,
    created_at_column=_SQLITE_CREATED_AT,
)

POSTGRES_SCHEMA_SQL = SCHEMA_TEMPLATE.format(
    id_column=_POSTGRES_ID_COLUMN,
    created_at_column=_POSTGRES_CREATED_AT,
)

# SQLite predates ADD COLUMN IF NOT EXISTS, so these are wrapped in try/except.
MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN verification_token TEXT",
    "ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT '2026-01-01 00:00:00'",
)

POSTGRES_MIGRATIONS: tuple[str, ...] = (
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TEXT NOT NULL DEFAULT '2026-01-01 00:00:00'",
)

# One-time data migrations, tracked by version in app_meta so they never re-run.
VERSIONED_MIGRATIONS: tuple[str, ...] = (
    # v1: current_hp previously defaulted to 0 meaning "unset"; -1 is the new sentinel.
    "UPDATE campaign_members SET current_hp = -1 WHERE current_hp = 0",
)

_init_lock = threading.Lock()
_initialized_keys: set[str] = set()
_session_secret_cache: dict[str, str] = {}
_pg_pool = None


def _q(sql: str) -> str:
    """Translate '?' placeholders to Postgres '%s' when needed."""
    return sql.replace("?", "%s") if IS_POSTGRES else sql


def _db_key() -> str:
    return DATABASE_URL if IS_POSTGRES else str(DB_PATH)


def _get_pool():
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = ConnectionPool(
            DATABASE_URL,
            min_size=0,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pg_pool


def close_database_connections() -> None:
    """Close pooled Postgres connections for one-off scripts and tests."""
    global _pg_pool
    if _pg_pool is not None:
        _pg_pool.close()
        _pg_pool = None


def _migrate_legacy_data_dir() -> None:
    """Copy old repo-local runtime files to the external data directory once."""
    if DB_PATH != DEFAULT_DB_PATH:
        return
    if DB_PATH.parent == LEGACY_DATA_DIR or DB_PATH.exists():
        return
    legacy_db = LEGACY_DATA_DIR / DB_PATH.name
    if not legacy_db.exists():
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    for legacy_file in LEGACY_DATA_DIR.glob(f"{DB_PATH.name}*"):
        shutil.copy2(legacy_file, DB_PATH.parent / legacy_file.name)
    legacy_outbox = LEGACY_DATA_DIR / "dev_email_outbox.log"
    if legacy_outbox.exists():
        shutil.copy2(legacy_outbox, DB_PATH.parent / legacy_outbox.name)


def connect():
    """Return a DB connection usable as a context manager.

    Postgres: a pooled connection (returned to the pool and committed on
    context exit). SQLite: a fresh connection (committed on context exit).
    Both support conn.execute(sql, params) returning a cursor.
    """
    if IS_POSTGRES:
        return _get_pool().connection()
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def initialize_database() -> None:
    """Create tables and run migrations. Cheap after the first call per database."""
    key = _db_key()
    if key in _initialized_keys:
        return
    with _init_lock:
        if key in _initialized_keys:
            return
        if IS_POSTGRES:
            with connect() as conn:
                conn.execute(POSTGRES_SCHEMA_SQL)
                for migration in POSTGRES_MIGRATIONS:
                    conn.execute(migration)
                _run_versioned_migrations(conn)
                conn.commit()
        else:
            _migrate_legacy_data_dir()
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            with connect() as conn:
                # WAL lets simultaneous readers/writers coexist without
                # "database is locked" errors once multiple players are online.
                conn.execute("PRAGMA journal_mode = WAL")
                conn.executescript(SCHEMA_SQL)
                for migration in MIGRATIONS:
                    try:
                        conn.execute(migration)
                    except sqlite3.OperationalError as exc:
                        if "duplicate column name" not in str(exc).lower():
                            raise
                _run_versioned_migrations(conn)
                conn.commit()
        _initialized_keys.add(key)


def _run_versioned_migrations(conn) -> None:
    row = conn.execute("SELECT value FROM app_meta WHERE key = 'schema_version'").fetchone()
    version = int(row["value"]) if row else 0
    for index, migration in enumerate(VERSIONED_MIGRATIONS, start=1):
        if index > version:
            conn.execute(migration)
    conn.execute(
        _q(
            "INSERT INTO app_meta (key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
        ),
        (str(len(VERSIONED_MIGRATIONS)),),
    )


def _insert_returning_id(conn, sql: str, params: tuple) -> int:
    """Run an INSERT and return the new row id on either dialect."""
    if IS_POSTGRES:
        row = conn.execute(_q(sql) + " RETURNING id", params).fetchone()
        return int(row["id"])
    cursor = conn.execute(sql, params)
    return int(cursor.lastrowid)


def get_session_secret() -> str:
    """Stable per-database secret used to sign login session tokens.

    Cached in-process: this runs on every page load/reconnect via
    restore_session, so it must not cost a DB round-trip each time.
    """
    key = _db_key()
    cached = _session_secret_cache.get(key)
    if cached:
        return cached
    initialize_database()
    with connect() as conn:
        row = conn.execute("SELECT value FROM app_meta WHERE key = 'session_secret'").fetchone()
        if row:
            secret = row["value"]
        else:
            secret = secrets.token_hex(32)
            conn.execute(_q("INSERT INTO app_meta (key, value) VALUES ('session_secret', ?)"), (secret,))
            conn.commit()
    _session_secret_cache[key] = secret
    return secret


def _row_to_dict(row) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _rows_to_dicts(rows: Iterable) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def create_user(email: str, password_hash: str, display_name: str, verification_token: str) -> tuple[bool, str]:
    initialize_database()
    try:
        with connect() as conn:
            conn.execute(
                _q(
                    """
                    INSERT INTO users (email, password_hash, display_name, email_verified, verification_token)
                    VALUES (?, ?, ?, 0, ?)
                    """
                ),
                (email, password_hash, display_name, verification_token),
            )
            conn.commit()
        return True, "created"
    except _INTEGRITY_ERRORS:
        user = get_user_by_email(email)
        if user and not int(user["email_verified"]):
            with connect() as conn:
                conn.execute(
                    _q(
                        """
                        UPDATE users
                        SET password_hash = ?, display_name = ?, verification_token = ?
                        WHERE email = ?
                        """
                    ),
                    (password_hash, display_name, verification_token, email),
                )
                conn.commit()
            return True, "resent"
        return False, "exists"


def get_user_by_email(email: str) -> dict[str, Any] | None:
    initialize_database()
    with connect() as conn:
        row = conn.execute(_q("SELECT * FROM users WHERE email = ?"), (email,)).fetchone()
    return _row_to_dict(row)


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    initialize_database()
    with connect() as conn:
        row = conn.execute(_q("SELECT * FROM users WHERE id = ?"), (user_id,)).fetchone()
    return _row_to_dict(row)


def verify_user_email(email: str, token: str) -> bool:
    initialize_database()
    with connect() as conn:
        result = conn.execute(
            _q(
                """
                UPDATE users
                SET email_verified = 1, verification_token = NULL
                WHERE email = ? AND verification_token = ?
                """
            ),
            (email, token),
        )
        rowcount = result.rowcount
        conn.commit()
    return rowcount == 1


def list_user_characters(user_id: int) -> list[dict[str, Any]]:
    initialize_database()
    aggregate = "string_agg(ca.name, ', ')" if IS_POSTGRES else "group_concat(ca.name, ', ')"
    with connect() as conn:
        rows = conn.execute(
            _q(
                f"""
                SELECT
                    c.*,
                    COALESCE({aggregate}, '') AS campaign_names
                FROM characters c
                LEFT JOIN campaign_members cm ON cm.character_id = c.id
                LEFT JOIN campaigns ca ON ca.id = cm.campaign_id
                WHERE c.owner_user_id = ?
                GROUP BY c.id
                ORDER BY c.id DESC
                """
            ),
            (user_id,),
        ).fetchall()
    return _rows_to_dicts(rows)


def get_character(character_id: int, owner_user_id: int) -> dict[str, Any] | None:
    """Fetch a character only if it belongs to the given user."""
    initialize_database()
    with connect() as conn:
        row = conn.execute(
            _q("SELECT * FROM characters WHERE id = ? AND owner_user_id = ?"),
            (character_id, owner_user_id),
        ).fetchone()
    return _row_to_dict(row)


def create_character(user_id: int, character: dict[str, Any]) -> int:
    initialize_database()
    with connect() as conn:
        character_id = _insert_returning_id(
            conn,
            """
            INSERT INTO characters (
                owner_user_id, name, ancestry, character_class, background, level,
                strength, dexterity, constitution, intelligence, wisdom, charisma,
                armor_name, has_shield, skill_proficiencies, save_proficiencies, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                character["name"],
                character["ancestry"],
                character["character_class"],
                character["background"],
                int(character["level"]),
                int(character["str"]),
                int(character["dex"]),
                int(character["con"]),
                int(character["int"]),
                int(character["wis"]),
                int(character["cha"]),
                character["armor"],
                1 if character["shield"] else 0,
                character["skills"],
                character["saves"],
                character["notes"],
            ),
        )
        conn.commit()
        return character_id


def update_character(character_id: int, owner_user_id: int, character: dict[str, Any]) -> bool:
    """Update a character's fields; ownership is enforced in the WHERE clause."""
    initialize_database()
    with connect() as conn:
        result = conn.execute(
            _q(
                """
                UPDATE characters SET
                    name = ?, ancestry = ?, character_class = ?, background = ?, level = ?,
                    strength = ?, dexterity = ?, constitution = ?, intelligence = ?, wisdom = ?, charisma = ?,
                    armor_name = ?, has_shield = ?, skill_proficiencies = ?, save_proficiencies = ?, notes = ?
                WHERE id = ? AND owner_user_id = ?
                """
            ),
            (
                character["name"],
                character["ancestry"],
                character["character_class"],
                character["background"],
                int(character["level"]),
                int(character["str"]),
                int(character["dex"]),
                int(character["con"]),
                int(character["int"]),
                int(character["wis"]),
                int(character["cha"]),
                character["armor"],
                1 if character["shield"] else 0,
                character["skills"],
                character["saves"],
                character["notes"],
                character_id,
                owner_user_id,
            ),
        )
        rowcount = result.rowcount
        conn.commit()
    return rowcount == 1


def delete_character(character_id: int, owner_user_id: int) -> bool:
    """Delete a character and detach it from any campaign memberships."""
    initialize_database()
    with connect() as conn:
        result = conn.execute(
            _q("DELETE FROM characters WHERE id = ? AND owner_user_id = ?"),
            (character_id, owner_user_id),
        )
        if result.rowcount == 0:
            return False
        conn.execute(
            _q("UPDATE campaign_members SET character_id = NULL, current_hp = ? WHERE character_id = ?"),
            (HP_UNSET, character_id),
        )
        conn.commit()
    return True


def list_user_campaigns(user_id: int) -> list[dict[str, Any]]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(
            _q(
                """
                SELECT
                    ca.*,
                    cm.role,
                    cm.character_id,
                    COALESCE(ch.name, '') AS character_name
                FROM campaign_members cm
                JOIN campaigns ca ON ca.id = cm.campaign_id
                LEFT JOIN characters ch ON ch.id = cm.character_id
                WHERE cm.user_id = ?
                ORDER BY ca.id DESC
                """
            ),
            (user_id,),
        ).fetchall()
    return _rows_to_dicts(rows)


def create_campaign(user_id: int, name: str, next_session: str, invite_code: str) -> int:
    initialize_database()
    with connect() as conn:
        campaign_id = _insert_returning_id(
            conn,
            """
            INSERT INTO campaigns (host_user_id, name, invite_code, next_session, session_log, shared_notes)
            VALUES (?, ?, ?, ?, '', '')
            """,
            (user_id, name, invite_code, next_session),
        )
        conn.execute(
            _q(
                """
                INSERT INTO campaign_members (campaign_id, user_id, character_id, role, current_hp, location, active_conditions)
                VALUES (?, ?, NULL, 'dm', -1, 'Campaign start', '')
                """
            ),
            (campaign_id, user_id),
        )
        conn.commit()
        return campaign_id


def get_campaign(campaign_id: int, user_id: int) -> dict[str, Any] | None:
    initialize_database()
    with connect() as conn:
        row = conn.execute(
            _q(
                """
                SELECT
                    ca.*,
                    cm.role,
                    cm.character_id AS my_character_id,
                    COALESCE(ch.name, '') AS my_character_name
                FROM campaigns ca
                JOIN campaign_members cm ON cm.campaign_id = ca.id
                LEFT JOIN characters ch ON ch.id = cm.character_id
                WHERE ca.id = ? AND cm.user_id = ?
                """
            ),
            (campaign_id, user_id),
        ).fetchone()
    return _row_to_dict(row)


def find_campaign_by_invite(invite_code: str) -> dict[str, Any] | None:
    initialize_database()
    with connect() as conn:
        row = conn.execute(_q("SELECT * FROM campaigns WHERE invite_code = ?"), (invite_code,)).fetchone()
    return _row_to_dict(row)


def join_campaign(
    user_id: int,
    invite_code: str,
    character_id: int | None = None,
    initial_hp: int = HP_UNSET,
) -> tuple[bool, str]:
    """Join a campaign by invite code, optionally attaching one of your characters.

    Re-joining an existing membership with a character updates the attachment
    instead of failing, so players can fix or change their character.
    """
    campaign = find_campaign_by_invite(invite_code)
    if campaign is None:
        return False, "not_found"
    if character_id is not None and get_character(character_id, user_id) is None:
        return False, "character_not_owned"
    initialize_database()
    with connect() as conn:
        existing = conn.execute(
            _q("SELECT id, character_id FROM campaign_members WHERE campaign_id = ? AND user_id = ?"),
            (campaign["id"], user_id),
        ).fetchone()
        if existing:
            if character_id is not None and character_id != existing["character_id"]:
                conn.execute(
                    _q("UPDATE campaign_members SET character_id = ?, current_hp = ? WHERE id = ?"),
                    (character_id, initial_hp, existing["id"]),
                )
                conn.commit()
                return True, "character_updated"
            return True, "already_joined"
        conn.execute(
            _q(
                """
                INSERT INTO campaign_members (campaign_id, user_id, character_id, role, current_hp, location, active_conditions)
                VALUES (?, ?, ?, 'player', ?, 'Not assigned yet', '')
                """
            ),
            (campaign["id"], user_id, character_id, initial_hp),
        )
        conn.commit()
    return True, "joined"


def assign_character_to_campaign(
    campaign_id: int,
    user_id: int,
    character_id: int,
    initial_hp: int = HP_UNSET,
) -> tuple[bool, str]:
    """Attach (or swap) one of the user's characters on an existing membership."""
    if get_character(character_id, user_id) is None:
        return False, "character_not_owned"
    initialize_database()
    with connect() as conn:
        result = conn.execute(
            _q("UPDATE campaign_members SET character_id = ?, current_hp = ? WHERE campaign_id = ? AND user_id = ?"),
            (character_id, initial_hp, campaign_id, user_id),
        )
        rowcount = result.rowcount
        conn.commit()
    if rowcount == 0:
        return False, "not_a_member"
    return True, "assigned"


def update_member_hp(member_id: int, current_hp: int) -> None:
    initialize_database()
    with connect() as conn:
        conn.execute(
            _q("UPDATE campaign_members SET current_hp = ? WHERE id = ?"),
            (max(0, int(current_hp)), member_id),
        )
        conn.commit()


def update_campaign_details(
    campaign_id: int,
    *,
    next_session: str | None = None,
    session_log: str | None = None,
    shared_notes: str | None = None,
) -> None:
    """Update any provided campaign text fields; None fields are left untouched."""
    fields = {
        "next_session": next_session,
        "session_log": session_log,
        "shared_notes": shared_notes,
    }
    updates = {column: value for column, value in fields.items() if value is not None}
    if not updates:
        return
    initialize_database()
    assignments = ", ".join(f"{column} = ?" for column in updates)
    with connect() as conn:
        conn.execute(
            _q(f"UPDATE campaigns SET {assignments} WHERE id = ?"),
            (*updates.values(), campaign_id),
        )
        conn.commit()


def get_dm_notes(campaign_id: int) -> str:
    initialize_database()
    with connect() as conn:
        row = conn.execute(
            _q("SELECT body FROM dm_notes WHERE campaign_id = ? ORDER BY id LIMIT 1"),
            (campaign_id,),
        ).fetchone()
    return row["body"] if row else ""


def save_dm_notes(campaign_id: int, body: str) -> None:
    initialize_database()
    with connect() as conn:
        row = conn.execute(
            _q("SELECT id FROM dm_notes WHERE campaign_id = ? ORDER BY id LIMIT 1"),
            (campaign_id,),
        ).fetchone()
        if row:
            conn.execute(_q("UPDATE dm_notes SET body = ? WHERE id = ?"), (body, row["id"]))
        else:
            conn.execute(
                _q("INSERT INTO dm_notes (campaign_id, title, body) VALUES (?, 'Session notes', ?)"),
                (campaign_id, body),
            )
        conn.commit()


def list_campaign_members(campaign_id: int) -> list[dict[str, Any]]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(
            _q(
                """
                SELECT
                    cm.id,
                    cm.user_id,
                    cm.character_id,
                    cm.role,
                    cm.current_hp,
                    cm.location,
                    cm.active_conditions,
                    u.display_name,
                    u.email,
                    ch.name AS character,
                    ch.character_class,
                    ch.level,
                    ch.constitution
                FROM campaign_members cm
                JOIN users u ON u.id = cm.user_id
                LEFT JOIN characters ch ON ch.id = cm.character_id
                WHERE cm.campaign_id = ?
                ORDER BY cm.role, u.display_name
                """
            ),
            (campaign_id,),
        ).fetchall()
    return _rows_to_dicts(rows)


def list_campaign_npcs(campaign_id: int) -> list[dict[str, Any]]:
    initialize_database()
    with connect() as conn:
        rows = conn.execute(
            _q("SELECT * FROM npcs WHERE campaign_id = ? ORDER BY id DESC"),
            (campaign_id,),
        ).fetchall()
    return _rows_to_dicts(rows)


def create_npc(campaign_id: int, npc: dict[str, Any]) -> None:
    initialize_database()
    with connect() as conn:
        conn.execute(
            _q(
                """
                INSERT INTO npcs (campaign_id, name, armor_class, current_hp, max_hp, key_stats)
                VALUES (?, ?, ?, ?, ?, ?)
                """
            ),
            (campaign_id, npc["name"], npc["ac"], npc["current_hp"], npc["max_hp"], npc["stats"]),
        )
        conn.commit()


def update_npc_hp(npc_id: int, current_hp: int) -> None:
    initialize_database()
    with connect() as conn:
        conn.execute(
            _q("UPDATE npcs SET current_hp = ? WHERE id = ?"),
            (max(0, int(current_hp)), npc_id),
        )
        conn.commit()
