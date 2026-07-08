"""Seed CC-BY-4.0 SRD rules data from dnd5eapi.co into local sqlite tables."""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

import requests

from dnd_and_beyond.data_access import connect, initialize_database


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger("seed_srd")

API_BASE = os.getenv("SRD_API_BASE", "https://www.dnd5eapi.co").rstrip("/")
SOURCE = "dnd5eapi.co"

ENDPOINTS = {
    "rules_races": "/api/races",
    "rules_classes": "/api/classes",
    "rules_backgrounds": "/api/backgrounds",
    "rules_spells": "/api/spells",
    "rules_equipment": "/api/equipment",
    "rules_conditions": "/api/conditions",
}


def fetch_json(path: str) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def upsert_payload(table: str, payload: dict[str, Any]) -> None:
    index = payload["index"]
    name = payload["name"]
    payload_json = json.dumps(payload, sort_keys=True)
    with connect() as conn:
        if table == "rules_classes":
            conn.execute(
                """
                INSERT INTO rules_classes ("index", name, hit_die, source, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT("index") DO UPDATE SET
                    name=excluded.name,
                    hit_die=excluded.hit_die,
                    source=excluded.source,
                    payload_json=excluded.payload_json
                """,
                (index, name, int(payload.get("hit_die", 8)), SOURCE, payload_json),
            )
        elif table == "rules_spells":
            conn.execute(
                """
                INSERT INTO rules_spells ("index", name, level, source, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT("index") DO UPDATE SET
                    name=excluded.name,
                    level=excluded.level,
                    source=excluded.source,
                    payload_json=excluded.payload_json
                """,
                (index, name, int(payload.get("level", 0)), SOURCE, payload_json),
            )
        elif table == "rules_equipment":
            category = payload.get("equipment_category", {}).get("name", "")
            conn.execute(
                """
                INSERT INTO rules_equipment ("index", name, equipment_category, source, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT("index") DO UPDATE SET
                    name=excluded.name,
                    equipment_category=excluded.equipment_category,
                    source=excluded.source,
                    payload_json=excluded.payload_json
                """,
                (index, name, category, SOURCE, payload_json),
            )
        else:
            conn.execute(
                f"""
                INSERT INTO {table} ("index", name, source, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT("index") DO UPDATE SET
                    name=excluded.name,
                    source=excluded.source,
                    payload_json=excluded.payload_json
                """,
                (index, name, SOURCE, payload_json),
            )
        conn.commit()


def seed_endpoint(table: str, endpoint: str) -> int:
    listing = fetch_json(endpoint)
    count = 0
    for item in listing.get("results", []):
        detail = fetch_json(item["url"])
        upsert_payload(table, detail)
        count += 1
    LOGGER.info("Seeded %s records into %s", count, table)
    return count


def main() -> int:
    initialize_database()
    totals = {table: seed_endpoint(table, endpoint) for table, endpoint in ENDPOINTS.items()}
    missing = [table for table, total in totals.items() if total == 0]
    if missing:
        LOGGER.error("No records were seeded for: %s", ", ".join(missing))
        return 1
    LOGGER.info("SRD seed complete. Attribution: SRD 5.1 CC-BY-4.0 via %s", SOURCE)
    return 0


if __name__ == "__main__":
    sys.exit(main())

