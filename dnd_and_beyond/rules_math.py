"""Official 5e derived-stat calculations used by the builder and tests."""

from __future__ import annotations

from dataclasses import dataclass


CLASS_HIT_DICE: dict[str, int] = {
    "barbarian": 12,
    "bard": 8,
    "cleric": 8,
    "druid": 8,
    "fighter": 10,
    "monk": 8,
    "paladin": 10,
    "ranger": 10,
    "rogue": 8,
    "sorcerer": 6,
    "warlock": 8,
    "wizard": 6,
}

SPELLCASTING_ABILITIES: dict[str, str] = {
    "bard": "cha",
    "cleric": "wis",
    "druid": "wis",
    "paladin": "cha",
    "ranger": "wis",
    "sorcerer": "cha",
    "warlock": "cha",
    "wizard": "int",
}

SKILL_ABILITIES: dict[str, str] = {
    "acrobatics": "dex",
    "animal handling": "wis",
    "arcana": "int",
    "athletics": "str",
    "deception": "cha",
    "history": "int",
    "insight": "wis",
    "intimidation": "cha",
    "investigation": "int",
    "medicine": "wis",
    "nature": "int",
    "perception": "wis",
    "performance": "cha",
    "persuasion": "cha",
    "religion": "int",
    "sleight of hand": "dex",
    "stealth": "dex",
    "survival": "wis",
}


@dataclass(frozen=True)
class Armor:
    name: str
    category: str
    base_ac: int
    dex_cap: int | None = None
    stealth_disadvantage: bool = False


ARMOR: dict[str, Armor] = {
    "none": Armor("None", "unarmored", 10, None),
    "padded": Armor("Padded", "light", 11, None, True),
    "leather": Armor("Leather", "light", 11, None),
    "studded leather": Armor("Studded Leather", "light", 12, None),
    "hide": Armor("Hide", "medium", 12, 2),
    "chain shirt": Armor("Chain Shirt", "medium", 13, 2),
    "scale mail": Armor("Scale Mail", "medium", 14, 2, True),
    "breastplate": Armor("Breastplate", "medium", 14, 2),
    "half plate": Armor("Half Plate", "medium", 15, 2, True),
    "ring mail": Armor("Ring Mail", "heavy", 14, 0, True),
    "chain mail": Armor("Chain Mail", "heavy", 16, 0, True),
    "splint": Armor("Splint", "heavy", 17, 0, True),
    "plate": Armor("Plate", "heavy", 18, 0, True),
}


def ability_modifier(score: int) -> int:
    """Return the official 5e ability modifier for an ability score."""
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    """Return the 5e proficiency bonus for character level 1 through 20."""
    if not 1 <= level <= 20:
        raise ValueError("Level must be between 1 and 20.")
    return 2 + ((level - 1) // 4)


def hit_die_for_class(class_name: str) -> int:
    key = class_name.strip().lower()
    if key not in CLASS_HIT_DICE:
        raise ValueError(f"Unknown SRD class: {class_name}")
    return CLASS_HIT_DICE[key]


def average_hit_die_gain(hit_die: int) -> int:
    """Return the fixed HP gain printed for leveling in 5e class rules."""
    return (hit_die // 2) + 1


def max_hp(class_name: str, level: int, constitution_score: int) -> int:
    """Calculate max HP using max first-level HP and fixed average after level 1."""
    if level < 1:
        raise ValueError("Level must be at least 1.")
    hit_die = hit_die_for_class(class_name)
    con_mod = ability_modifier(constitution_score)
    return hit_die + con_mod + ((average_hit_die_gain(hit_die) + con_mod) * (level - 1))


def armor_class(dexterity_score: int, armor_name: str = "none", shield: bool = False) -> int:
    """Calculate AC for standard SRD armor and optional shield."""
    armor = ARMOR.get(armor_name.strip().lower())
    if armor is None:
        raise ValueError(f"Unknown SRD armor: {armor_name}")
    dex_mod = ability_modifier(dexterity_score)
    if armor.category == "heavy":
        dex_bonus = 0
    elif armor.dex_cap is None:
        dex_bonus = dex_mod
    else:
        dex_bonus = min(dex_mod, armor.dex_cap)
    return armor.base_ac + dex_bonus + (2 if shield else 0)


def initiative_bonus(dexterity_score: int, other_bonus: int = 0) -> int:
    return ability_modifier(dexterity_score) + other_bonus


def saving_throw_bonus(
    ability_score: int,
    level: int,
    proficient: bool = False,
    other_bonus: int = 0,
) -> int:
    return ability_modifier(ability_score) + (proficiency_bonus(level) if proficient else 0) + other_bonus


def skill_bonus(
    ability_score: int,
    level: int,
    proficient: bool = False,
    expertise: bool = False,
    other_bonus: int = 0,
) -> int:
    multiplier = 2 if expertise else 1
    prof = proficiency_bonus(level) * multiplier if proficient or expertise else 0
    return ability_modifier(ability_score) + prof + other_bonus


def spellcasting_ability(class_name: str) -> str | None:
    return SPELLCASTING_ABILITIES.get(class_name.strip().lower())


def spell_save_dc(class_name: str, level: int, ability_scores: dict[str, int]) -> int | None:
    ability = spellcasting_ability(class_name)
    if ability is None:
        return None
    return 8 + proficiency_bonus(level) + ability_modifier(ability_scores[ability])


def spell_attack_bonus(class_name: str, level: int, ability_scores: dict[str, int]) -> int | None:
    ability = spellcasting_ability(class_name)
    if ability is None:
        return None
    return proficiency_bonus(level) + ability_modifier(ability_scores[ability])


def format_bonus(value: int | None) -> str:
    if value is None:
        return "-"
    return f"+{value}" if value >= 0 else str(value)
