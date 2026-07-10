"""Permanently purge accounts and user-created app data.

Rule catalogs and app metadata are intentionally retained so the app is ready
for a new group immediately after a reset.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def load_database_url(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing production environment file: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "DATABASE_URL" and value.strip():
            os.environ["DATABASE_URL"] = value.strip()
            return
    raise RuntimeError("DATABASE_URL is missing from the production environment file.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Permanently purge DND and Beyond accounts and user-created data.")
    parser.add_argument("--confirm", action="store_true", help="Required before permanent deletion.")
    parser.add_argument("--dry-run", action="store_true", help="Show records that would be removed without deleting them.")
    parser.add_argument(
        "--production-env-file",
        help="Load DATABASE_URL from this env file to target the production Postgres database.",
    )
    args = parser.parse_args()

    if args.production_env_file:
        try:
            load_database_url(Path(args.production_env_file))
        except (FileNotFoundError, RuntimeError) as exc:
            print(exc, file=sys.stderr)
            return 1

    # Import after the optional env file is loaded so the correct database is selected.
    from dnd_and_beyond import data_access

    try:
        counts = data_access.user_data_counts()
        target = "production Postgres" if data_access.IS_POSTGRES else "local SQLite"
        total = sum(counts.values())
        print(f"Target: {target}")
        print(f"User-created records: {total}")
        print(", ".join(f"{table}={count}" for table, count in counts.items()))

        if args.dry_run:
            print("DRY_RUN_OK")
            return 0
        if not args.confirm:
            print("Refusing to delete data without --confirm.", file=sys.stderr)
            return 2

        data_access.purge_user_data()
        after = data_access.user_data_counts()
        if any(after.values()):
            print("Purge did not complete cleanly.", file=sys.stderr)
            return 1
        print("PURGE_OK")
        return 0
    finally:
        data_access.close_database_connections()


if __name__ == "__main__":
    raise SystemExit(main())
