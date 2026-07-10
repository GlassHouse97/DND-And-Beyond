import re

from dnd_and_beyond.srd_catalog import (
    SPELLS,
    WEAPONS,
    describe_spell,
    describe_weapon,
    spells_for_class,
    weapon_attack_ability,
)
from dnd_and_beyond.state import CLASS_OPTIONS, _spell_hover_text

DICE_PATTERN = re.compile(r"^\d+d\d+$")

SCORES = {"str": 8, "dex": 16, "con": 14, "int": 15, "wis": 12, "cha": 10}


def test_weapon_catalog_is_well_formed():
    for weapon in WEAPONS.values():
        assert DICE_PATTERN.match(weapon.die), weapon.name
        assert weapon.category in ("simple", "martial")
        assert weapon.kind in ("melee", "ranged")
        assert weapon.ability in ("str", "dex", "finesse")
        if weapon.kind == "ranged":
            assert weapon.range_ft is not None, weapon.name
        if weapon.versatile_die:
            assert DICE_PATTERN.match(weapon.versatile_die), weapon.name


def test_finesse_and_ranged_weapons_use_best_ability():
    dagger = WEAPONS["Dagger"]
    assert weapon_attack_ability(dagger, SCORES) == "dex"
    assert weapon_attack_ability(dagger, {**SCORES, "str": 18}) == "str"
    assert weapon_attack_ability(WEAPONS["Longbow"], {**SCORES, "str": 18}) == "dex"
    assert weapon_attack_ability(WEAPONS["Mace"], SCORES) == "str"


def test_weapon_description_matches_starter_sheet_voice():
    # DEX 16 (+3) at level 1 (+2 prof) -> 1d20 + 5 to hit, 1d6 + 3 damage.
    info = describe_weapon(WEAPONS["Shortbow"], SCORES, 1)
    assert info["attack_bonus"] == "+5"
    assert info["damage"] == "1d6 +3 piercing"
    assert "Roll 1d20 +5 to see if you hit" in info["text"]
    assert "80 feet" in info["text"] and "320 feet" in info["text"]


def test_spell_catalog_is_well_formed():
    assert len(SPELLS) == 319
    for spell in SPELLS.values():
        assert spell.level in range(10), spell.name
        assert spell.kind in ("attack", "save", "auto", "heal", "utility"), spell.name
        assert spell.school
        assert spell.cast and spell.range and spell.duration
        assert spell.components
        assert spell.text
        for klass in spell.classes:
            assert klass in CLASS_OPTIONS, f"{spell.name}: unknown class {klass}"
        if spell.kind == "save":
            assert spell.save, spell.name
        if "{dice}" in spell.text:
            assert spell.dice, spell.name


def test_every_caster_class_has_spells_and_martials_have_none():
    for klass in ("Bard", "Cleric", "Druid", "Paladin", "Ranger", "Sorcerer", "Warlock", "Wizard"):
        options = spells_for_class(klass)
        assert options, klass
        assert any(spell.level > 0 for spell in options), f"{klass} has no leveled spells"
    for klass in ("Barbarian", "Fighter", "Monk", "Rogue"):
        assert spells_for_class(klass) == [], klass
    assert len(spells_for_class("Wizard")) >= 200
    assert len(spells_for_class("Cleric")) >= 100


def test_spell_description_fills_real_numbers():
    # Wizard INT 15 (+2), level 1: DC 12, attack +4.
    info = describe_spell(SPELLS["Fire Bolt"], "Wizard", 1, SCORES)
    assert "+4" in info["headline"]
    assert "1d10" in info["headline"]
    save_info = describe_spell(SPELLS["Sacred Flame"], "Cleric", 1, {**SCORES, "wis": 16})
    assert "DC 13 Dexterity save" in save_info["headline"]
    assert "DC: 13" in save_info["text"]


def test_cantrip_damage_scales_with_level():
    assert "1d10" in describe_spell(SPELLS["Fire Bolt"], "Wizard", 4, SCORES)["headline"]
    assert "2d10" in describe_spell(SPELLS["Fire Bolt"], "Wizard", 5, SCORES)["headline"]
    assert "3d10" in describe_spell(SPELLS["Fire Bolt"], "Wizard", 11, SCORES)["headline"]
    assert "4d10" in describe_spell(SPELLS["Fire Bolt"], "Wizard", 17, SCORES)["headline"]
    # Leveled spells do not scale this way.
    assert "3d6" in describe_spell(SPELLS["Burning Hands"], "Wizard", 17, SCORES)["headline"]


def test_spell_hover_text_keeps_current_math_and_a_concise_effect():
    info = describe_spell(SPELLS["Fire Bolt"], "Wizard", 5, SCORES)
    hover = _spell_hover_text(SPELLS["Fire Bolt"], info["headline"])
    assert hover.startswith(info["headline"] + ".")
    assert "You hurl" in hover
    assert len(hover) <= len(info["headline"]) + 222


def test_non_caster_gets_safe_placeholders():
    # Never rendered for non-casters in the UI, but must not crash and must
    # show an em-dash where the attack bonus would be.
    info = describe_spell(SPELLS["Fire Bolt"], "Fighter", 1, SCORES)
    assert "—" in info["text"]
