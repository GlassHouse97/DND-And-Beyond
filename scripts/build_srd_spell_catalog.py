"""Download and normalize the SRD 5.1 spell catalog for offline app use."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests


API_BASE = "https://www.dnd5eapi.co"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "dnd_and_beyond" / "data" / "srd_spells_2014.json"


def fetch_json(path: str) -> dict[str, Any]:
    response = requests.get(f"{API_BASE}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def normalize_spell(payload: dict[str, Any]) -> dict[str, Any]:
    damage = payload.get("damage", {})
    dc = payload.get("dc", {})
    return {
        "index": payload["index"],
        "name": payload["name"],
        "level": int(payload["level"]),
        "school": payload.get("school", {}).get("name", ""),
        "casting_time": payload.get("casting_time", ""),
        "range": payload.get("range", ""),
        "components": payload.get("components", []),
        "material": payload.get("material") or "",
        "duration": payload.get("duration", ""),
        "concentration": bool(payload.get("concentration")),
        "ritual": bool(payload.get("ritual")),
        "description": payload.get("desc", []),
        "higher_level": payload.get("higher_level", []),
        "damage_type": damage.get("damage_type", {}).get("name", ""),
        "damage_at_slot_level": damage.get("damage_at_slot_level", {}),
        "damage_at_character_level": damage.get("damage_at_character_level", {}),
        "save_type": dc.get("dc_type", {}).get("name", ""),
        "save_success": dc.get("dc_success", ""),
        "attack_type": payload.get("attack_type", ""),
        "classes": [entry["name"] for entry in payload.get("classes", [])],
    }


def main() -> int:
    listing = fetch_json("/api/2014/spells")
    entries = listing.get("results", [])
    with ThreadPoolExecutor(max_workers=16) as executor:
        details = list(executor.map(lambda entry: fetch_json(entry["url"]), entries))
    spells = sorted((normalize_spell(detail) for detail in details), key=lambda spell: spell["name"])
    if len(spells) != 319:
        raise RuntimeError(f"Expected 319 SRD spells, received {len(spells)}.")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(spells, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(spells)} SRD spells to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
