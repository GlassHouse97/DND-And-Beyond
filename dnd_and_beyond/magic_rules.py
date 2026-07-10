"""SRD 5.1 spellcasting rules shared by the builder and character sheet.

This module deliberately models access by class. Ancestry magic is represented
as a separate trait elsewhere, never mixed into a class spell list.
"""

from __future__ import annotations

from dataclasses import dataclass

from dnd_and_beyond.rules_math import ability_modifier, proficiency_bonus, spellcasting_ability


STANDARD_SLOT_TABLE: tuple[tuple[int, ...], ...] = (
    (2,), (3,), (4, 2), (4, 3), (4, 3, 2), (4, 3, 3), (4, 3, 3, 1),
    (4, 3, 3, 2), (4, 3, 3, 3, 1), (4, 3, 3, 3, 2), (4, 3, 3, 3, 2, 1),
    (4, 3, 3, 3, 2, 1), (4, 3, 3, 3, 2, 1, 1), (4, 3, 3, 3, 2, 1, 1),
    (4, 3, 3, 3, 2, 1, 1, 1), (4, 3, 3, 3, 2, 1, 1, 1),
    (4, 3, 3, 3, 2, 1, 1, 1, 1), (4, 3, 3, 3, 3, 1, 1, 1, 1),
    (4, 3, 3, 3, 3, 2, 1, 1, 1), (4, 3, 3, 3, 3, 2, 2, 1, 1),
)


@dataclass(frozen=True)
class CastingProfile:
    mode: str  # none | known | prepared | spellbook | pact
    ability: str | None
    cantrip_table: tuple[int, ...] = ()
    known_table: tuple[int, ...] = ()


FULL_CANTRIP_TABLES = {
    "Bard": (2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4),
    "Cleric": (3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5),
    "Druid": (2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4),
    "Sorcerer": (4, 4, 4, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6),
    "Warlock": (2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4),
    "Wizard": (3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5),
}

CASTING_PROFILES: dict[str, CastingProfile] = {
    "Bard": CastingProfile("known", "cha", FULL_CANTRIP_TABLES["Bard"],
                           (4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 15, 16, 18, 19, 19, 20, 22, 22, 22)),
    "Cleric": CastingProfile("prepared", "wis", FULL_CANTRIP_TABLES["Cleric"]),
    "Druid": CastingProfile("prepared", "wis", FULL_CANTRIP_TABLES["Druid"]),
    "Paladin": CastingProfile("prepared", "cha"),
    "Ranger": CastingProfile("known", "wis", (),
                             (0, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11)),
    "Sorcerer": CastingProfile("known", "cha", FULL_CANTRIP_TABLES["Sorcerer"],
                                (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12, 13, 13, 14, 14, 15, 15, 15, 15)),
    "Warlock": CastingProfile("pact", "cha", FULL_CANTRIP_TABLES["Warlock"],
                               (2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15)),
    "Wizard": CastingProfile("spellbook", "int", FULL_CANTRIP_TABLES["Wizard"]),
}

LIFE_DOMAIN_SPELLS: tuple[tuple[int, tuple[str, str]], ...] = (
    (1, ("Bless", "Cure Wounds")), (3, ("Lesser Restoration", "Spiritual Weapon")),
    (5, ("Beacon of Hope", "Revivify")), (7, ("Death Ward", "Guardian of Faith")),
    (9, ("Mass Cure Wounds", "Raise Dead")),
)


def _level(level: int) -> int:
    return max(1, min(20, int(level)))


def casting_profile(class_name: str) -> CastingProfile:
    return CASTING_PROFILES.get(class_name.strip().title(), CastingProfile("none", None))


def standard_spell_slots(class_name: str, level: int) -> dict[int, int]:
    """Standard long-rest slots for full and half casters."""
    profile = casting_profile(class_name)
    level = _level(level)
    if profile.mode not in {"known", "prepared", "spellbook"} or class_name == "Warlock":
        return {}
    caster_level = level if class_name not in {"Paladin", "Ranger"} else level // 2
    if caster_level < 1:
        return {}
    return {index + 1: value for index, value in enumerate(STANDARD_SLOT_TABLE[caster_level - 1]) if value}


def pact_magic_slots(level: int) -> dict[int, int]:
    """Warlock Pact Magic slots; these refresh on a short rest."""
    level = _level(level)
    slot_level = 1 if level <= 2 else 2 if level <= 4 else 3 if level <= 6 else 4 if level <= 8 else 5
    slot_count = 1 if level == 1 else 2 if level <= 10 else 3 if level <= 16 else 4
    return {slot_level: slot_count}


def spell_slots(class_name: str, level: int) -> dict[int, int]:
    return pact_magic_slots(level) if class_name == "Warlock" else standard_spell_slots(class_name, level)


def max_spell_level(class_name: str, level: int) -> int:
    slots = spell_slots(class_name, level)
    return max(slots, default=0)


def cantrips_known(class_name: str, level: int) -> int:
    table = casting_profile(class_name).cantrip_table
    return table[_level(level) - 1] if table else 0


def spells_known_limit(class_name: str, level: int) -> int:
    table = casting_profile(class_name).known_table
    return table[_level(level) - 1] if table else 0


def spellbook_limit(level: int) -> int:
    """Wizard spellbook size from class progression, excluding found scrolls."""
    return 6 + 2 * (_level(level) - 1)


def prepared_spell_limit(class_name: str, level: int, ability_score: int) -> int:
    profile = casting_profile(class_name)
    if profile.mode not in {"prepared", "spellbook"} or not spell_slots(class_name, level):
        return 0
    class_level = _level(level)
    base = class_level if class_name != "Paladin" else class_level // 2
    return max(1, base + ability_modifier(ability_score))


def magical_secrets_count(level: int) -> int:
    level = _level(level)
    return (2 if level >= 10 else 0) + (2 if level >= 14 else 0) + (2 if level >= 18 else 0)


def mystic_arcanum_levels(level: int) -> tuple[int, ...]:
    level = _level(level)
    return tuple(spell_level for required, spell_level in ((11, 6), (13, 7), (15, 8), (17, 9)) if level >= required)


def always_prepared_spells(class_name: str, level: int) -> list[str]:
    """Life Domain is the currently supported SRD cleric domain."""
    if class_name != "Cleric":
        return []
    return [spell for required, spells in LIFE_DOMAIN_SPELLS if _level(level) >= required for spell in spells]


def casting_summary(class_name: str, level: int, ability_scores: dict[str, int]) -> dict[str, object]:
    profile = casting_profile(class_name)
    level = _level(level)
    ability = spellcasting_ability(class_name)
    ability_score = int(ability_scores.get(ability or "", 10))
    slots = spell_slots(class_name, level)
    return {
        "mode": profile.mode,
        "ability": ability.upper() if ability else "",
        "save_dc": 8 + proficiency_bonus(level) + ability_modifier(ability_score) if ability else None,
        "attack_bonus": proficiency_bonus(level) + ability_modifier(ability_score) if ability else None,
        "cantrips": cantrips_known(class_name, level),
        "known_limit": spells_known_limit(class_name, level),
        "prepared_limit": prepared_spell_limit(class_name, level, ability_score),
        "spellbook_limit": spellbook_limit(level) if profile.mode == "spellbook" else 0,
        "max_spell_level": max(slots, default=0),
        "slots": slots,
        "slot_recovery": "short rest" if profile.mode == "pact" else "long rest",
        "magical_secrets": magical_secrets_count(level) if class_name == "Bard" else 0,
        "mystic_arcanum": mystic_arcanum_levels(level) if class_name == "Warlock" else (),
        "always_prepared": always_prepared_spells(class_name, level),
    }
