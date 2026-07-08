from dnd_and_beyond.state import _die_size, _hp_percent, _invite_code_seed, _safe_int


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
