from dnd_and_beyond.magic_rules import (
    always_prepared_spells,
    cantrips_known,
    casting_summary,
    magical_secrets_count,
    max_spell_level,
    mystic_arcanum_levels,
    pact_magic_slots,
    prepared_spell_limit,
    spell_slots,
    spellbook_limit,
    spells_known_limit,
)
from dnd_and_beyond.state import _ancestry_innate_spells


SCORES = {"str": 8, "dex": 14, "con": 12, "int": 16, "wis": 14, "cha": 16}


def test_level_one_wizard_uses_spellbook_rules_and_correct_dc():
    summary = casting_summary("Wizard", 1, SCORES)
    assert summary["cantrips"] == 3
    assert summary["spellbook_limit"] == 6
    assert summary["prepared_limit"] == 4
    assert summary["save_dc"] == 13
    assert summary["attack_bonus"] == 5
    assert summary["slots"] == {1: 2}


def test_warlock_uses_pact_magic_not_standard_slots():
    assert pact_magic_slots(5) == {3: 2}
    assert spell_slots("Warlock", 5) == {3: 2}
    assert max_spell_level("Warlock", 5) == 3
    assert spell_slots("Warlock", 11) == {5: 3}
    assert mystic_arcanum_levels(17) == (6, 7, 8, 9)


def test_half_casters_begin_at_second_level_and_have_no_cantrips():
    assert spell_slots("Paladin", 1) == {}
    assert prepared_spell_limit("Paladin", 1, 16) == 0
    assert spell_slots("Paladin", 2) == {1: 2}
    assert prepared_spell_limit("Paladin", 2, 16) == 4
    assert cantrips_known("Paladin", 20) == 0
    assert spells_known_limit("Ranger", 1) == 0
    assert spells_known_limit("Ranger", 2) == 2


def test_known_and_prepared_progressions_are_class_specific():
    assert spells_known_limit("Bard", 1) == 4
    assert spells_known_limit("Sorcerer", 20) == 15
    assert spellbook_limit(10) == 24
    assert magical_secrets_count(9) == 0
    assert magical_secrets_count(18) == 6
    assert always_prepared_spells("Cleric", 5) == [
        "Bless", "Cure Wounds", "Lesser Restoration", "Spiritual Weapon", "Beacon of Hope", "Revivify"
    ]


def test_innate_ancestry_magic_is_separate_from_class_access():
    assert _ancestry_innate_spells("Tiefling", 1) == ["Thaumaturgy"]
    assert _ancestry_innate_spells("Tiefling", 5) == ["Thaumaturgy", "Hellish Rebuke", "Darkness"]
    assert _ancestry_innate_spells("Forest Gnome", 1) == ["Minor Illusion"]
    assert _ancestry_innate_spells("High Elf", 1, "Fire Bolt") == ["Fire Bolt"]
