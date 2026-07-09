"""Curated SRD weapons and spells with plain-English, per-character math.

Descriptions follow the Dragons of Stormwreck Isle starter-sheet voice:
"Roll 1d20 + 5 to see if you hit. If you do, the target takes 1d6 + 3
piercing damage." All content is 5.1 SRD (CC-BY-4.0).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dnd_and_beyond.rules_math import (
    ability_modifier,
    format_bonus,
    proficiency_bonus,
    spell_attack_bonus,
    spell_save_dc,
    spellcasting_ability,
)


# --------------------------------------------------------------------------
# Weapons
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Weapon:
    name: str
    category: str          # "simple" | "martial"
    die: str               # e.g. "1d8"
    damage_type: str       # "slashing" | "piercing" | "bludgeoning"
    ability: str           # "str" | "dex" | "finesse" (finesse = best of the two)
    kind: str              # "melee" | "ranged"
    thrown: tuple[int, int] | None = None    # (normal, long) feet
    range_ft: tuple[int, int] | None = None  # ranged weapons: (normal, long)
    versatile_die: str | None = None         # die when used two-handed
    properties: tuple[str, ...] = field(default_factory=tuple)


WEAPONS: dict[str, Weapon] = {
    weapon.name: weapon
    for weapon in (
        Weapon("Dagger", "simple", "1d4", "piercing", "finesse", "melee", thrown=(20, 60), properties=("light",)),
        Weapon("Handaxe", "simple", "1d6", "slashing", "str", "melee", thrown=(20, 60), properties=("light",)),
        Weapon("Javelin", "simple", "1d6", "piercing", "str", "melee", thrown=(30, 120)),
        Weapon("Mace", "simple", "1d6", "bludgeoning", "str", "melee"),
        Weapon("Quarterstaff", "simple", "1d6", "bludgeoning", "str", "melee", versatile_die="1d8"),
        Weapon("Spear", "simple", "1d6", "piercing", "str", "melee", thrown=(20, 60), versatile_die="1d8"),
        Weapon("Light Crossbow", "simple", "1d8", "piercing", "dex", "ranged", range_ft=(80, 320), properties=("loading", "two-handed")),
        Weapon("Shortbow", "simple", "1d6", "piercing", "dex", "ranged", range_ft=(80, 320), properties=("two-handed",)),
        Weapon("Sling", "simple", "1d4", "bludgeoning", "dex", "ranged", range_ft=(30, 120)),
        Weapon("Battleaxe", "martial", "1d8", "slashing", "str", "melee", versatile_die="1d10"),
        Weapon("Greataxe", "martial", "1d12", "slashing", "str", "melee", properties=("heavy", "two-handed")),
        Weapon("Greatsword", "martial", "2d6", "slashing", "str", "melee", properties=("heavy", "two-handed")),
        Weapon("Longsword", "martial", "1d8", "slashing", "str", "melee", versatile_die="1d10"),
        Weapon("Rapier", "martial", "1d8", "piercing", "finesse", "melee"),
        Weapon("Scimitar", "martial", "1d6", "slashing", "finesse", "melee", properties=("light",)),
        Weapon("Shortsword", "martial", "1d6", "piercing", "finesse", "melee", properties=("light",)),
        Weapon("Warhammer", "martial", "1d8", "bludgeoning", "str", "melee", versatile_die="1d10"),
        Weapon("Longbow", "martial", "1d8", "piercing", "dex", "ranged", range_ft=(150, 600), properties=("heavy", "two-handed")),
    )
}

WEAPON_NAMES: tuple[str, ...] = tuple(sorted(WEAPONS))


def weapon_attack_ability(weapon: Weapon, scores: dict[str, int]) -> str:
    """Which ability the character actually uses for this weapon."""
    if weapon.kind == "ranged":
        return "dex"
    if weapon.ability == "finesse":
        return "dex" if scores["dex"] >= scores["str"] else "str"
    return weapon.ability


def describe_weapon(weapon: Weapon, scores: dict[str, int], level: int) -> dict[str, str]:
    """Stormwreck-style attack text with this character's real numbers."""
    ability = weapon_attack_ability(weapon, scores)
    modifier = ability_modifier(scores[ability])
    attack_bonus = modifier + proficiency_bonus(level)
    damage_mod = f" {format_bonus(modifier)}" if modifier else ""

    if weapon.kind == "ranged":
        normal, far = weapon.range_ft
        how = (
            f"Shoot at a target up to {normal} feet away, "
            f"or up to {far} feet with disadvantage on the attack roll."
        )
    else:
        how = f"In melee (against a target within 5 feet of you), you can attack with your {weapon.name.lower()}."
        if weapon.thrown:
            normal, far = weapon.thrown
            how += (
                f" You can also throw it at a target up to {normal} feet away, "
                f"or up to {far} feet with disadvantage on the attack roll."
            )

    roll = (
        f"Roll 1d20 {format_bonus(attack_bonus)} to see if you hit. "
        f"If you do, the target takes {weapon.die}{damage_mod} {weapon.damage_type} damage."
    )
    extras = []
    if weapon.versatile_die:
        extras.append(f"Held in two hands it deals {weapon.versatile_die}{damage_mod} instead.")
    if "loading" in weapon.properties:
        extras.append("Loading: one shot per turn.")

    return {
        "attack_bonus": format_bonus(attack_bonus),
        "damage": f"{weapon.die}{damage_mod} {weapon.damage_type}",
        "uses": ability.upper(),
        "text": " ".join([how, roll, *extras]),
    }


# --------------------------------------------------------------------------
# Spells
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Spell:
    name: str
    level: int             # 0 = cantrip
    school: str
    classes: tuple[str, ...]
    cast: str              # "1 action", "1 bonus action", "1 reaction"
    range: str
    duration: str
    kind: str              # "attack" | "save" | "auto" | "heal" | "utility"
    text: str              # plain-English effect; {dice}, {dc}, {atk}, {mod} filled in
    dice: str | None = None
    damage_type: str | None = None
    save: str | None = None
    concentration: bool = False
    cantrip_scaling: bool = False   # dice count grows at levels 5/11/17


SPELLS: dict[str, Spell] = {
    spell.name: spell
    for spell in (
        # ----- Cantrips -----
        Spell("Fire Bolt", 0, "Evocation", ("Sorcerer", "Wizard"), "1 action", "120 feet", "Instant", "attack",
              "Hurl a mote of fire. Roll 1d20 {atk} to hit; the target takes {dice} fire damage. Ignites flammable objects.",
              dice="1d10", damage_type="fire", cantrip_scaling=True),
        Spell("Ray of Frost", 0, "Evocation", ("Sorcerer", "Wizard"), "1 action", "60 feet", "Instant", "attack",
              "A beam of frigid light. Roll 1d20 {atk} to hit; the target takes {dice} cold damage and its speed drops by 10 feet until your next turn.",
              dice="1d8", damage_type="cold", cantrip_scaling=True),
        Spell("Shocking Grasp", 0, "Evocation", ("Sorcerer", "Wizard"), "1 action", "Touch", "Instant", "attack",
              "Lightning springs from your hand. Roll 1d20 {atk} (with advantage if the target wears metal armor); it takes {dice} lightning damage and can't take reactions until its next turn.",
              dice="1d8", damage_type="lightning", cantrip_scaling=True),
        Spell("Eldritch Blast", 0, "Evocation", ("Warlock",), "1 action", "120 feet", "Instant", "attack",
              "A beam of crackling energy. Roll 1d20 {atk} to hit; the target takes {dice} force damage. Extra beams at higher levels attack separately.",
              dice="1d10", damage_type="force", cantrip_scaling=True),
        Spell("Produce Flame", 0, "Conjuration", ("Druid",), "1 action", "Self / 30 feet", "10 minutes", "attack",
              "A flame in your palm sheds light; you can hurl it. Roll 1d20 {atk} to hit; the target takes {dice} fire damage.",
              dice="1d8", damage_type="fire", cantrip_scaling=True),
        Spell("Sacred Flame", 0, "Evocation", ("Cleric",), "1 action", "60 feet", "Instant", "save",
              "Flame-like radiance descends on a creature. It must succeed on a DC {dc} Dexterity save or take {dice} radiant damage — cover gives no protection.",
              dice="1d8", damage_type="radiant", save="Dexterity", cantrip_scaling=True),
        Spell("Vicious Mockery", 0, "Enchantment", ("Bard",), "1 action", "60 feet", "Instant", "save",
              "Unleash a string of magical insults. The target must succeed on a DC {dc} Wisdom save or take {dice} psychic damage and have disadvantage on its next attack roll.",
              dice="1d4", damage_type="psychic", save="Wisdom", cantrip_scaling=True),
        Spell("Guidance", 0, "Divination", ("Cleric", "Druid"), "1 action", "Touch", "1 minute", "utility",
              "Touch a willing creature. Once before the spell ends, it can add 1d4 to one ability check of its choice.",
              concentration=True),
        Spell("Light", 0, "Evocation", ("Bard", "Cleric", "Sorcerer", "Wizard"), "1 action", "Touch", "1 hour", "utility",
              "An object you touch sheds bright light in a 20-foot radius and dim light for another 20."),
        Spell("Mage Hand", 0, "Conjuration", ("Bard", "Sorcerer", "Warlock", "Wizard"), "1 action", "30 feet", "1 minute", "utility",
              "A spectral floating hand manipulates objects, opens doors, or carries up to 10 pounds."),
        Spell("Minor Illusion", 0, "Illusion", ("Bard", "Sorcerer", "Warlock", "Wizard"), "1 action", "30 feet", "1 minute", "utility",
              "Create a sound or a small image (no bigger than a 5-foot cube). An Investigation check against DC {dc} sees through it."),
        Spell("Prestidigitation", 0, "Transmutation", ("Bard", "Sorcerer", "Warlock", "Wizard"), "1 action", "10 feet", "Up to 1 hour", "utility",
              "Minor magical tricks: spark, snuff, clean, soil, chill, warm, or flavor small things."),
        Spell("Thaumaturgy", 0, "Transmutation", ("Cleric",), "1 action", "30 feet", "Up to 1 minute", "utility",
              "Minor divine wonder: booming voice, flickering flames, tremors, or slamming doors."),
        Spell("Druidcraft", 0, "Transmutation", ("Druid",), "1 action", "30 feet", "Instant", "utility",
              "Whisper to the spirits of nature: predict the weather, bloom a flower, or light a campfire."),

        # ----- 1st level -----
        Spell("Magic Missile", 1, "Evocation", ("Sorcerer", "Wizard"), "1 action", "120 feet", "Instant", "auto",
              "Three glowing darts strike targets you choose — they always hit. Each dart deals 1d4 + 1 force damage.",
              dice="3x(1d4+1)", damage_type="force"),
        Spell("Cure Wounds", 1, "Evocation", ("Bard", "Cleric", "Druid", "Paladin", "Ranger"), "1 action", "Touch", "Instant", "heal",
              "A creature you touch regains 1d8 {mod} hit points."),
        Spell("Healing Word", 1, "Evocation", ("Bard", "Cleric", "Druid"), "1 bonus action", "60 feet", "Instant", "heal",
              "Call out to a creature you can see: it regains 1d4 {mod} hit points. A bonus action, so you can still attack."),
        Spell("Bless", 1, "Enchantment", ("Cleric", "Paladin"), "1 action", "30 feet", "1 minute", "utility",
              "Up to three creatures each add 1d4 to every attack roll and saving throw while the spell lasts.",
              concentration=True),
        Spell("Guiding Bolt", 1, "Evocation", ("Cleric",), "1 action", "120 feet", "1 round", "attack",
              "A flash of light streaks at a creature. Roll 1d20 {atk} to hit; it takes {dice} radiant damage and the next attack against it has advantage.",
              dice="4d6", damage_type="radiant"),
        Spell("Burning Hands", 1, "Evocation", ("Sorcerer", "Wizard"), "1 action", "Self (15-foot cone)", "Instant", "save",
              "Flames sweep from your fingertips. Each creature in a 15-foot cone makes a DC {dc} Dexterity save, taking {dice} fire damage on a failure or half on a success.",
              dice="3d6", damage_type="fire", save="Dexterity"),
        Spell("Thunderwave", 1, "Evocation", ("Bard", "Druid", "Sorcerer", "Wizard"), "1 action", "Self (15-foot cube)", "Instant", "save",
              "A wave of thunderous force. Each creature within 15 feet makes a DC {dc} Constitution save: {dice} thunder damage and pushed 10 feet on a failure, half damage on a success. Audible 300 feet away.",
              dice="2d8", damage_type="thunder", save="Constitution"),
        Spell("Sleep", 1, "Enchantment", ("Bard", "Sorcerer", "Wizard"), "1 action", "90 feet", "1 minute", "utility",
              "Roll 5d8: that many hit points of creatures fall unconscious, weakest first, until they take damage or are shaken awake."),
        Spell("Shield", 1, "Abjuration", ("Sorcerer", "Wizard"), "1 reaction", "Self", "1 round", "utility",
              "When you're hit by an attack, raise an invisible barrier: +5 AC until your next turn, and magic missile can't touch you."),
        Spell("Mage Armor", 1, "Abjuration", ("Sorcerer", "Wizard"), "1 action", "Touch", "8 hours", "utility",
              "Protective magic wraps an unarmored creature: its AC becomes 13 + its DEX modifier for 8 hours."),
        Spell("Detect Magic", 1, "Divination", ("Bard", "Cleric", "Druid", "Paladin", "Ranger", "Sorcerer", "Wizard"), "1 action", "Self", "10 minutes", "utility",
              "Sense magic within 30 feet and see a faint aura around visible magical things. Can be cast as a ritual (no spell slot).",
              concentration=True),
        Spell("Charm Person", 1, "Enchantment", ("Bard", "Druid", "Sorcerer", "Warlock", "Wizard"), "1 action", "30 feet", "1 hour", "save",
              "A humanoid must succeed on a DC {dc} Wisdom save (with advantage if you're fighting it) or regard you as a friendly acquaintance for an hour.",
              save="Wisdom"),
        Spell("Faerie Fire", 1, "Evocation", ("Bard", "Druid"), "1 action", "60 feet", "1 minute", "save",
              "Objects and creatures in a 20-foot cube glow. Creatures that fail a DC {dc} Dexterity save can't hide, and attacks against them have advantage.",
              save="Dexterity", concentration=True),
        Spell("Entangle", 1, "Conjuration", ("Druid",), "1 action", "90 feet", "1 minute", "save",
              "Grasping weeds fill a 20-foot square. Creatures there must succeed on a DC {dc} Strength save or be restrained until they break free.",
              save="Strength", concentration=True),
        Spell("Goodberry", 1, "Transmutation", ("Druid", "Ranger"), "1 action", "Touch", "Instant", "heal",
              "Create ten magic berries. Eating one restores 1 hit point and nourishes a creature for a day."),
        Spell("Hunter's Mark", 1, "Divination", ("Ranger",), "1 bonus action", "90 feet", "1 hour", "utility",
              "Mark a creature as your quarry: your weapon attacks against it deal an extra 1d6 damage, and you have advantage tracking it.",
              concentration=True),
        Spell("Divine Favor", 1, "Evocation", ("Paladin",), "1 bonus action", "Self", "1 minute", "utility",
              "Your weapon attacks deal an extra 1d4 radiant damage while the spell lasts.",
              concentration=True),
        Spell("Hex", 1, "Enchantment", ("Warlock",), "1 bonus action", "90 feet", "1 hour", "utility",
              "Curse a creature: your attacks against it deal an extra 1d6 necrotic damage, and it has disadvantage on checks with one ability you choose.",
              concentration=True),
        Spell("Command", 1, "Enchantment", ("Cleric", "Paladin"), "1 action", "60 feet", "1 round", "save",
              "Speak a one-word command. The target must succeed on a DC {dc} Wisdom save or obey: approach, drop, flee, grovel, or halt.",
              save="Wisdom"),

        # ----- 2nd level -----
        Spell("Spiritual Weapon", 2, "Evocation", ("Cleric",), "1 bonus action", "60 feet", "1 minute", "attack",
              "A floating spectral weapon attacks where you point it. Roll 1d20 {atk} to hit; it deals {dice} {mod} force damage. A bonus action each turn to move and strike again.",
              dice="1d8", damage_type="force"),
        Spell("Hold Person", 2, "Enchantment", ("Bard", "Cleric", "Druid", "Sorcerer", "Warlock", "Wizard"), "1 action", "60 feet", "1 minute", "save",
              "A humanoid must succeed on a DC {dc} Wisdom save or be paralyzed. It re-saves each turn; attacks within 5 feet of it are automatic crits.",
              save="Wisdom", concentration=True),
        Spell("Misty Step", 2, "Conjuration", ("Sorcerer", "Warlock", "Wizard"), "1 bonus action", "Self", "Instant", "utility",
              "Vanish in silvery mist and teleport up to 30 feet to a spot you can see."),
        Spell("Invisibility", 2, "Illusion", ("Bard", "Sorcerer", "Warlock", "Wizard"), "1 action", "Touch", "1 hour", "utility",
              "A creature you touch turns invisible until it attacks or casts a spell.",
              concentration=True),
        Spell("Flaming Sphere", 2, "Conjuration", ("Druid", "Wizard"), "1 action", "60 feet", "1 minute", "save",
              "A rolling ball of fire. Creatures ending their turn beside it make a DC {dc} Dexterity save, taking {dice} fire damage on a failure or half on a success. Ram it into things as a bonus action.",
              dice="2d6", damage_type="fire", save="Dexterity", concentration=True),
        Spell("Scorching Ray", 2, "Evocation", ("Sorcerer", "Wizard"), "1 action", "120 feet", "Instant", "attack",
              "Hurl three rays of fire at any targets. Roll 1d20 {atk} for each; every hit deals {dice} fire damage.",
              dice="2d6", damage_type="fire"),
        Spell("Shatter", 2, "Evocation", ("Bard", "Sorcerer", "Warlock", "Wizard"), "1 action", "60 feet", "Instant", "save",
              "A painful ringing burst. Creatures in a 10-foot sphere make a DC {dc} Constitution save: {dice} thunder damage on a failure, half on a success.",
              dice="3d8", damage_type="thunder", save="Constitution"),
        Spell("Lesser Restoration", 2, "Abjuration", ("Bard", "Cleric", "Druid", "Paladin", "Ranger"), "1 action", "Touch", "Instant", "heal",
              "Touch a creature to end one disease or one condition: blinded, deafened, paralyzed, or poisoned."),
        Spell("Aid", 2, "Abjuration", ("Cleric", "Paladin"), "1 action", "30 feet", "8 hours", "heal",
              "Bolster up to three creatures: their hit point maximum and current hit points rise by 5 for 8 hours."),
        Spell("Moonbeam", 2, "Evocation", ("Druid",), "1 action", "120 feet", "1 minute", "save",
              "A silvery beam in a 5-foot cylinder. Creatures entering it or starting there make a DC {dc} Constitution save, taking {dice} radiant damage on a failure or half on a success.",
              dice="2d10", damage_type="radiant", save="Constitution", concentration=True),
        Spell("Pass Without Trace", 2, "Abjuration", ("Druid", "Ranger"), "1 action", "Self", "1 hour", "utility",
              "A veil of shadows: you and companions within 30 feet add +10 to Stealth checks and can't be tracked.",
              concentration=True),
    )
}

SPELL_NAMES: tuple[str, ...] = tuple(SPELLS)

SPELL_LEVEL_LABELS: dict[int, str] = {0: "Cantrip", 1: "1st level", 2: "2nd level"}


def spells_for_class(character_class: str) -> list[Spell]:
    return [spell for spell in SPELLS.values() if character_class in spell.classes]


def _cantrip_dice(base: str, level: int) -> str:
    """Cantrip damage grows at character levels 5, 11, and 17."""
    count, _, die = base.partition("d")
    steps = 1 + (level >= 5) + (level >= 11) + (level >= 17)
    return f"{int(count) * steps}d{die}"


def describe_spell(spell: Spell, character_class: str, level: int, scores: dict[str, int]) -> dict[str, str]:
    """Fill a spell's template with this character's real numbers."""
    dc = spell_save_dc(character_class, level, scores)
    atk = spell_attack_bonus(character_class, level, scores)
    ability = spellcasting_ability(character_class)
    modifier = ability_modifier(scores[ability]) if ability else 0

    dice = spell.dice or ""
    if spell.cantrip_scaling and spell.dice:
        dice = _cantrip_dice(spell.dice, level)

    text = spell.text
    text = text.replace("{dice}", dice)
    text = text.replace("{dc}", str(dc) if dc is not None else "—")
    text = text.replace("{atk}", format_bonus(atk) if atk is not None else "—")
    text = text.replace("{mod}", f"+ {modifier}" if modifier >= 0 else f"- {abs(modifier)}")

    if spell.kind == "attack":
        headline = f"Spell attack {format_bonus(atk)}" if atk is not None else "Spell attack"
        if dice:
            headline += f" · {dice} {spell.damage_type}"
    elif spell.kind == "save":
        headline = f"DC {dc} {spell.save} save" if dc is not None else f"{spell.save} save"
        if dice:
            headline += f" · {dice} {spell.damage_type}"
    elif spell.kind == "auto":
        headline = "Always hits"
    elif spell.kind == "heal":
        headline = "Healing"
    else:
        headline = "Utility"

    meta = f"{spell.cast} · {spell.range} · {spell.duration}"
    if spell.concentration:
        meta += " · concentration"

    return {
        "headline": headline,
        "meta": meta,
        "text": text,
        "level_label": SPELL_LEVEL_LABELS[spell.level],
    }
