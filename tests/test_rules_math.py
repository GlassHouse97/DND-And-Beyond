import pytest

from dnd_and_beyond.rules_math import (
    ability_modifier,
    armor_class,
    initiative_bonus,
    max_hp,
    proficiency_bonus,
    saving_throw_bonus,
    skill_bonus,
    spell_attack_bonus,
    spell_save_dc,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [(1, -5), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (18, 4), (20, 5)],
)
def test_ability_modifiers(score, expected):
    assert ability_modifier(score) == expected


@pytest.mark.parametrize(
    ("level", "expected"),
    [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6)],
)
def test_proficiency_bonus_by_level(level, expected):
    assert proficiency_bonus(level) == expected


def test_fighter_hp_uses_max_first_level_and_fixed_average_afterward():
    assert max_hp("fighter", level=5, constitution_score=16) == 49


def test_wizard_hp_uses_d6_fixed_average_after_first_level():
    assert max_hp("wizard", level=3, constitution_score=14) == 20


def test_armor_class_light_medium_heavy_and_shield_rules():
    assert armor_class(16, "studded leather", shield=False) == 15
    assert armor_class(18, "half plate", shield=True) == 19
    assert armor_class(8, "chain mail", shield=True) == 18


def test_skill_save_initiative_and_spellcasting_examples():
    assert initiative_bonus(14) == 2
    assert saving_throw_bonus(16, level=5, proficient=True) == 6
    assert skill_bonus(14, level=5, proficient=True) == 5
    assert skill_bonus(14, level=5, expertise=True) == 8

    scores = {"str": 8, "dex": 14, "con": 13, "int": 18, "wis": 12, "cha": 10}
    assert spell_save_dc("wizard", 9, scores) == 16
    assert spell_attack_bonus("wizard", 9, scores) == 8

