from dnd_and_beyond.state import (
    _ability_bonuses_for_ancestry,
    _apply_ancestry_bonuses,
    _die_size,
    _hp_percent,
    _invite_code_seed,
    _recommended_standard_array,
    _safe_int,
)


def test_safe_int_falls_back_for_blank_or_invalid_values():
    assert _safe_int("", 10) == 10
    assert _safe_int(None, 10) == 10
    assert _safe_int("not a number", 10) == 10


def test_safe_int_applies_bounds():
    assert _safe_int("0", 10, minimum=1, maximum=20) == 1
    assert _safe_int("25", 10, minimum=1, maximum=20) == 20
    assert _safe_int("12", 10, minimum=1, maximum=20) == 12


def test_die_size_accepts_supported_dice_and_falls_back():
    assert _die_size("d12") == 12
    assert _die_size("20") == 20
    assert _die_size("") == 20
    assert _die_size("d7") == 20


def test_hp_percent_is_clamped_and_safe_for_empty_hp_pools():
    assert _hp_percent(15, 30) == "50%"
    assert _hp_percent(40, 30) == "100%"
    assert _hp_percent(-5, 30) == "0%"
    assert _hp_percent(1, 0) == "0%"


def test_invite_code_seed_removes_slug_separators():
    assert _invite_code_seed("Smoke Campaign") == "SMOKEC"
    assert _invite_code_seed("!!!") == "QUEST"


def test_class_recommended_standard_array_uses_official_values():
    assert _recommended_standard_array("Druid") == {
        "wis": 15,
        "con": 14,
        "dex": 13,
        "int": 12,
        "cha": 10,
        "str": 8,
    }
    assert _recommended_standard_array("Wizard") == {
        "int": 15,
        "con": 14,
        "dex": 13,
        "wis": 12,
        "cha": 10,
        "str": 8,
    }


def test_ancestry_bonuses_apply_to_standard_array_scores():
    druid = _recommended_standard_array("Druid")
    assert _apply_ancestry_bonuses("Halfling", druid) == {
        "str": 8,
        "dex": 15,
        "con": 14,
        "int": 12,
        "wis": 15,
        "cha": 10,
    }
    wizard = _recommended_standard_array("Wizard")
    assert _apply_ancestry_bonuses("Gnome", wizard) == {
        "str": 8,
        "dex": 13,
        "con": 14,
        "int": 17,
        "wis": 12,
        "cha": 10,
    }


def test_half_elf_uses_player_chosen_bonus_scores():
    assert _ability_bonuses_for_ancestry("Half-Elf", "str", "wis") == {
        "str": 1,
        "dex": 0,
        "con": 0,
        "int": 0,
        "wis": 1,
        "cha": 2,
    }
