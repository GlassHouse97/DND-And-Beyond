"""Reflex state for account-owned characters and campaigns."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import random
import re
import secrets
from urllib.parse import parse_qs, urlparse
from typing import Any

import reflex as rx

from dnd_and_beyond import data_access
from dnd_and_beyond.email_service import send_verification_email
from dnd_and_beyond.rules_math import (
    ARMOR,
    SKILL_ABILITIES,
    ability_modifier,
    armor_class,
    format_bonus,
    max_hp,
    proficiency_bonus,
    skill_bonus,
    spell_attack_bonus,
    spell_save_dc,
)


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = 260_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return (
        f"pbkdf2_sha256${iterations}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(digest).decode('ascii')}"
    )


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(raw_salt)
        expected = base64.b64decode(raw_digest)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(raw_iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _sign_session(user_id: int) -> str:
    secret = data_access.get_session_secret()
    signature = hmac.new(secret.encode("utf-8"), str(user_id).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{user_id}.{signature}"


def _session_user_id(token: str) -> int:
    try:
        raw_id, signature = token.split(".", 1)
        user_id = int(raw_id)
    except ValueError:
        return 0
    secret = data_access.get_session_secret()
    expected = hmac.new(secret.encode("utf-8"), raw_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return user_id if hmac.compare_digest(expected, signature) else 0


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _invite_code_seed(name: str) -> str:
    return _slug(name).replace("-", "")[:6].upper() or "QUEST"


ABILITY_KEYS: tuple[str, ...] = ("str", "dex", "con", "int", "wis", "cha")
ABILITY_LABELS: dict[str, str] = {
    "str": "Strength",
    "dex": "Dexterity",
    "con": "Constitution",
    "int": "Intelligence",
    "wis": "Wisdom",
    "cha": "Charisma",
}
ABILITY_KEYS_BY_LABEL: dict[str, str] = {label: key for key, label in ABILITY_LABELS.items()}

STANDARD_ARRAY: tuple[int, ...] = (15, 14, 13, 12, 10, 8)

ANCESTRY_OPTIONS: tuple[str, ...] = (
    "Human",
    "Dwarf",
    "Elf",
    "Halfling",
    "Dragonborn",
    "Gnome",
    "Half-Elf",
    "Half-Orc",
    "Tiefling",
)

CLASS_OPTIONS: tuple[str, ...] = (
    "Barbarian",
    "Bard",
    "Cleric",
    "Druid",
    "Fighter",
    "Monk",
    "Paladin",
    "Ranger",
    "Rogue",
    "Sorcerer",
    "Warlock",
    "Wizard",
)

BACKGROUND_OPTIONS: tuple[str, ...] = ("Acolyte", "Criminal", "Folk Hero", "Noble", "Sage", "Soldier")

ANCESTRY_ABILITY_BONUSES: dict[str, dict[str, int]] = {
    "Human": {"str": 1, "dex": 1, "con": 1, "int": 1, "wis": 1, "cha": 1},
    "Dwarf": {"con": 2},
    "Elf": {"dex": 2},
    "Halfling": {"dex": 2},
    "Dragonborn": {"str": 2, "cha": 1},
    "Gnome": {"int": 2},
    "Half-Elf": {"cha": 2},
    "Half-Orc": {"str": 2, "con": 1},
    "Tiefling": {"int": 1, "cha": 2},
}

CLASS_ABILITY_PRIORITIES: dict[str, tuple[str, ...]] = {
    "Barbarian": ("str", "con", "dex", "wis", "cha", "int"),
    "Bard": ("cha", "dex", "con", "wis", "int", "str"),
    "Cleric": ("wis", "con", "str", "cha", "int", "dex"),
    "Druid": ("wis", "con", "dex", "int", "cha", "str"),
    "Fighter": ("str", "con", "dex", "wis", "cha", "int"),
    "Monk": ("dex", "wis", "con", "str", "cha", "int"),
    "Paladin": ("str", "cha", "con", "wis", "dex", "int"),
    "Ranger": ("dex", "wis", "con", "str", "int", "cha"),
    "Rogue": ("dex", "int", "cha", "con", "wis", "str"),
    "Sorcerer": ("cha", "con", "dex", "wis", "int", "str"),
    "Warlock": ("cha", "con", "dex", "wis", "int", "str"),
    "Wizard": ("int", "con", "dex", "wis", "cha", "str"),
}

CLASS_SAVE_PROFICIENCIES: dict[str, str] = {
    "Barbarian": "Strength, Constitution",
    "Bard": "Dexterity, Charisma",
    "Cleric": "Wisdom, Charisma",
    "Druid": "Intelligence, Wisdom",
    "Fighter": "Strength, Constitution",
    "Monk": "Strength, Dexterity",
    "Paladin": "Wisdom, Charisma",
    "Ranger": "Strength, Dexterity",
    "Rogue": "Dexterity, Intelligence",
    "Sorcerer": "Constitution, Charisma",
    "Warlock": "Wisdom, Charisma",
    "Wizard": "Intelligence, Wisdom",
}


SKILL_LABELS: dict[str, str] = {key: key.title() for key in SKILL_ABILITIES}
SKILL_LABELS["sleight of hand"] = "Sleight of Hand"

SKILL_LABELS_ORDERED: tuple[str, ...] = tuple(sorted(SKILL_LABELS.values()))
SKILL_ABILITY_BY_LABEL: dict[str, str] = {SKILL_LABELS[key]: ability for key, ability in SKILL_ABILITIES.items()}
SKILL_LABEL_BY_LOWER: dict[str, str] = {label.lower(): label for label in SKILL_LABELS_ORDERED}

ARMOR_CHOICES: tuple[str, ...] = ("none", "leather", "studded leather", "scale mail", "half plate", "chain mail", "plate")


def _recommended_standard_array(character_class: str) -> dict[str, int]:
    priorities = CLASS_ABILITY_PRIORITIES.get(character_class, CLASS_ABILITY_PRIORITIES["Fighter"])
    return dict(zip(priorities, STANDARD_ARRAY, strict=True))


def _ability_bonuses_for_ancestry(
    ancestry: str,
    half_elf_bonus_one: str = "dex",
    half_elf_bonus_two: str = "con",
) -> dict[str, int]:
    bonuses = {key: ANCESTRY_ABILITY_BONUSES.get(ancestry, {}).get(key, 0) for key in ABILITY_KEYS}
    if ancestry == "Half-Elf":
        choices = []
        for choice in (half_elf_bonus_one, half_elf_bonus_two):
            if choice in ABILITY_KEYS and choice != "cha" and choice not in choices:
                choices.append(choice)
        for choice in choices[:2]:
            bonuses[choice] += 1
    return bonuses


def _apply_ancestry_bonuses(
    ancestry: str,
    base_scores: dict[str, int],
    half_elf_bonus_one: str = "dex",
    half_elf_bonus_two: str = "con",
) -> dict[str, int]:
    bonuses = _ability_bonuses_for_ancestry(ancestry, half_elf_bonus_one, half_elf_bonus_two)
    return {key: max(1, min(30, int(base_scores[key]) + bonuses[key])) for key in ABILITY_KEYS}


def _format_ability_bonus(bonus: int) -> str:
    return f"+{bonus}" if bonus > 0 else "0"


def _extract_verification_token(value: str) -> str:
    raw_value = value.strip()
    if not raw_value:
        return ""
    parsed = urlparse(raw_value)
    query_token = parse_qs(parsed.query).get("verify_token", [""])[0]
    return query_token.strip() or raw_value


def _safe_int(value: Any, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        number = int(str(value).strip()) if value not in (None, "") else default
    except (TypeError, ValueError):
        number = default

    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _die_size(value: Any) -> int:
    raw_value = str(value or "d20").strip().lower().replace("d", "")
    die = _safe_int(raw_value, 20)
    return die if die in {4, 6, 8, 10, 12, 20, 100} else 20


def _hp_state(current_hp: int, max_hp_value: int) -> str:
    if max_hp_value <= 0:
        return "critical"
    ratio = current_hp / max_hp_value
    if ratio <= 0.33:
        return "critical"
    if ratio <= 0.66:
        return "hurt"
    return "healthy"


def _hp_percent(current_hp: int, max_hp_value: int) -> str:
    if max_hp_value <= 0:
        return "0%"
    percent = max(0, min(100, round((current_hp / max_hp_value) * 100)))
    return f"{percent}%"


def _choice_to_id(choice: str) -> int:
    """Extract the character id from a "Name (#7)" dropdown choice."""
    match = re.search(r"\(#(\d+)\)\s*$", choice or "")
    return int(match.group(1)) if match else 0


def _character_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "ancestry": row["ancestry"],
        "character_class": row["character_class"],
        "background": row["background"],
        "level": row["level"],
        "str": row["strength"],
        "dex": row["dexterity"],
        "con": row["constitution"],
        "int": row["intelligence"],
        "wis": row["wisdom"],
        "cha": row["charisma"],
        "armor": row["armor_name"],
        "shield": bool(row["has_shield"]),
        "skills": row["skill_proficiencies"],
        "saves": row["save_proficiencies"],
        "notes": row["notes"],
        "campaign_names": row.get("campaign_names", ""),
    }


def _blank_campaign() -> dict[str, Any]:
    return {
        "id": 0,
        "name": "No campaign selected",
        "invite_code": "",
        "next_session": "",
        "session_log": "",
        "shared_notes": "",
        "role": "",
        "my_character_id": 0,
        "my_character_name": "",
    }


class AppState(rx.State):
    # Persisted in the browser so websocket reconnects and refreshes land the
    # user back on the page they were viewing instead of bouncing them around.
    current_view: str = rx.LocalStorage("auth", name="dnd_current_view")
    auth_mode: str = "login"
    is_authenticated: bool = False
    user_id: int = 0
    user_email: str = ""
    display_name: str = ""
    auth_message: str = ""
    app_message: str = ""
    sheet_tab: str = "skills"
    campaign_tab: str = "hub"
    dm_tab: str = "status"
    dice_result: str = "Rolls will appear here."
    join_message: str = ""
    invite_code: str = ""
    current_turn: int = 0
    session_token: str = rx.LocalStorage("", name="dnd_session_token")

    selected_character_id: int = 0
    join_character_choice: str = ""
    assign_character_choice: str = ""
    builder_mode: str = "create"
    editing_character_id: int = 0
    # Bumped whenever the builder is (re)filled so uncontrolled inputs remount
    # and pick up fresh default values.
    builder_form_nonce: int = 0
    builder_name: str = ""
    builder_level: str = "1"
    builder_armor: str = "chain mail"
    builder_shield: bool = True
    builder_skill_selection: list[str] = ["Athletics", "Perception"]
    # Custom proficiency text from older characters that predates the picker.
    builder_skill_extra: str = ""
    builder_notes: str = ""
    builder_ancestry: str = "Human"
    builder_class: str = "Fighter"
    builder_background: str = "Soldier"
    builder_scores: dict[str, str] = {key: str(value) for key, value in _recommended_standard_array("Fighter").items()}
    builder_saves: str = CLASS_SAVE_PROFICIENCIES["Fighter"]
    builder_half_elf_bonus_one: str = "dex"
    builder_half_elf_bonus_two: str = "con"

    characters: list[dict[str, Any]] = []
    campaigns: list[dict[str, Any]] = []
    campaign: dict[str, Any] = _blank_campaign()
    members: list[dict[str, Any]] = []
    npcs: list[dict[str, Any]] = []
    initiative: list[dict[str, Any]] = []
    dm_notes: str = ""

    def restore_session(self) -> None:
        """Re-authenticate from the signed browser token so refreshes keep you logged in.

        Runs on every page load/reconnect. It must never move an already
        logged-in user off the page they are on, but it still revalidates the
        token so deleted or purged accounts cannot keep a stale in-memory view.
        """
        user_id = _session_user_id(self.session_token) if self.session_token else 0
        user = data_access.get_user_by_id(user_id) if user_id else None
        if user is None or not int(user["email_verified"]):
            if self.is_authenticated or self.session_token:
                self.logout()
            else:
                self.session_token = ""
                self.current_view = "auth"
            return
        if self.is_authenticated and self.user_id == int(user["id"]):
            # Token revalidated; this session already has its data loaded, so
            # don't redo the full multi-query load on every reconnect.
            return
        self.user_id = int(user["id"])
        self.user_email = user["email"]
        self.display_name = user["display_name"]
        self.is_authenticated = True
        if self.current_view == "auth":
            self.current_view = "dashboard"
        self.load_user_data()

    async def auth_submit(self, form_data: dict[str, Any]) -> None:
        if self.auth_mode == "register":
            await self.register(form_data)
        elif self.auth_mode == "verify":
            self.verify_email(form_data)
        else:
            await self.login(form_data)

    async def register(self, form_data: dict[str, Any]) -> None:
        email = form_data.get("email", "").strip().lower()
        password = form_data.get("password", "")
        name = form_data.get("display_name", "Table Friend").strip() or "Table Friend"
        if "@" not in email or len(password) < 8:
            self.auth_message = "Use an email and a password with at least 8 characters."
            return

        token = secrets.token_urlsafe(24)
        # pbkdf2 with 260k iterations takes ~100-200ms; keep it off the event
        # loop so one signup doesn't freeze every connected player.
        password_hash = await asyncio.to_thread(_hash_password, password)
        created, reason = data_access.create_user(email, password_hash, name, token)
        if not created:
            self.auth_message = "That email already has a verified account. Try logging in."
            return

        # Run the (potentially slow) email send off the event loop so one
        # registration can't stall every other connected player.
        delivery = await asyncio.to_thread(send_verification_email, email, token)
        self.auth_mode = "verify"
        self.auth_message = (
            "Verification email sent. For local testing, open "
            f"{delivery} and paste the code here."
            if reason in {"created", "resent"}
            else "Verification email sent."
        )

    def verify_email(self, form_data: dict[str, Any]) -> None:
        email = form_data.get("email", "").strip().lower()
        token = _extract_verification_token(form_data.get("verification_token", ""))
        if not email or not token:
            self.auth_message = "Enter your email and verification code."
            return
        if data_access.verify_user_email(email, token):
            self.auth_mode = "login"
            self.auth_message = "Email verified. You can log in now."
        else:
            self.auth_message = "That verification code did not match."

    async def login(self, form_data: dict[str, Any]) -> None:
        email = form_data.get("email", "").strip().lower()
        password = form_data.get("password", "")
        user = data_access.get_user_by_email(email)
        password_ok = user is not None and await asyncio.to_thread(
            _verify_password, password, user["password_hash"]
        )
        if not password_ok:
            self.auth_message = "Email or password was not recognized."
            return
        if not int(user["email_verified"]):
            self.auth_mode = "verify"
            self.auth_message = "Verify your email before logging in."
            return

        self.user_id = int(user["id"])
        self.user_email = user["email"]
        self.display_name = user["display_name"]
        self.is_authenticated = True
        self.session_token = _sign_session(self.user_id)
        self.auth_message = ""
        self.current_view = "dashboard"
        self.load_user_data()

    def logout(self) -> None:
        self.is_authenticated = False
        self.user_id = 0
        self.user_email = ""
        self.display_name = ""
        self.auth_message = ""
        self.app_message = ""
        self.session_token = ""
        self.selected_character_id = 0
        self.join_character_choice = ""
        self.assign_character_choice = ""
        self.characters = []
        self.campaigns = []
        self.campaign = _blank_campaign()
        self.members = []
        self.npcs = []
        self.initiative = []
        self.dm_notes = ""
        self.current_view = "auth"

    def load_user_data(self) -> None:
        if not self.user_id:
            return
        self.characters = [_character_from_row(row) for row in data_access.list_user_characters(self.user_id)]
        self.campaigns = data_access.list_user_campaigns(self.user_id)
        campaign_ids = [int(row["id"]) for row in self.campaigns]
        current_id = int(self.campaign.get("id") or 0)
        if campaign_ids:
            # Keep the campaign the user was looking at instead of snapping
            # back to the newest one on every refresh.
            self.select_campaign(current_id if current_id in campaign_ids else campaign_ids[0])
        else:
            self.campaign = _blank_campaign()
            self.members = []
            self.npcs = []
            self.initiative = []
            self.dm_notes = ""

    def select_campaign(self, campaign_id: int) -> None:
        selected = data_access.get_campaign(campaign_id, self.user_id)
        if selected is None:
            self.app_message = "That campaign is not attached to your account."
            return
        selected["my_character_id"] = int(selected.get("my_character_id") or 0)
        selected["my_character_name"] = selected.get("my_character_name") or ""
        self.campaign = selected
        self.invite_code = selected["invite_code"]
        self.members = [self._member_view(row) for row in data_access.list_campaign_members(campaign_id)]
        self.npcs = [self._npc_view(row) for row in data_access.list_campaign_npcs(campaign_id)]
        self.initiative = self._initiative_from_campaign()
        self.dm_notes = data_access.get_dm_notes(campaign_id) if selected.get("role") == "dm" else ""

    def open_campaign(self, campaign_id: int) -> None:
        self.select_campaign(campaign_id)
        self.campaign_tab = "hub"
        self.current_view = "campaign"

    def set_auth_mode(self, mode: str) -> None:
        self.auth_mode = mode
        self.auth_message = ""

    def set_sheet_tab(self, tab: str) -> None:
        self.sheet_tab = tab

    def set_campaign_tab(self, tab: str) -> None:
        self.campaign_tab = tab

    def set_dm_tab(self, tab: str) -> None:
        self.dm_tab = tab

    def set_join_character_choice(self, choice: str) -> None:
        self.join_character_choice = choice

    def set_assign_character_choice(self, choice: str) -> None:
        self.assign_character_choice = choice

    def set_builder_ancestry(self, ancestry: str) -> None:
        self.builder_ancestry = ancestry if ancestry in ANCESTRY_OPTIONS else "Human"

    def set_builder_class(self, character_class: str) -> None:
        self.builder_class = character_class if character_class in CLASS_OPTIONS else "Fighter"
        if self.builder_mode == "edit":
            # Editing an existing hero: changing class must not wipe their scores.
            return
        self.builder_scores = {
            key: str(value)
            for key, value in _recommended_standard_array(self.builder_class).items()
        }
        self.builder_saves = CLASS_SAVE_PROFICIENCIES.get(self.builder_class, CLASS_SAVE_PROFICIENCIES["Fighter"])

    def set_builder_background(self, background: str) -> None:
        self.builder_background = background if background in BACKGROUND_OPTIONS else "Soldier"

    def set_builder_level(self, value: str) -> None:
        self.builder_level = str(_safe_int(value, 1, minimum=1, maximum=20))

    def set_builder_armor(self, armor: str) -> None:
        self.builder_armor = armor if armor in ARMOR_CHOICES else "none"

    def set_builder_shield(self, checked: bool) -> None:
        self.builder_shield = bool(checked)

    def toggle_builder_skill(self, label: str) -> None:
        if label not in SKILL_ABILITY_BY_LABEL:
            return
        selected = set(self.builder_skill_selection)
        if label in selected:
            selected.discard(label)
        else:
            selected.add(label)
        self.builder_skill_selection = [name for name in SKILL_LABELS_ORDERED if name in selected]

    def set_half_elf_bonus_one(self, label: str) -> None:
        ability = ABILITY_KEYS_BY_LABEL.get(label, "dex")
        if ability == "cha":
            ability = "dex"
        if ability == self.builder_half_elf_bonus_two:
            self.builder_half_elf_bonus_two = "con" if ability != "con" else "dex"
        self.builder_half_elf_bonus_one = ability

    def set_half_elf_bonus_two(self, label: str) -> None:
        ability = ABILITY_KEYS_BY_LABEL.get(label, "con")
        if ability == "cha":
            ability = "con"
        if ability == self.builder_half_elf_bonus_one:
            self.builder_half_elf_bonus_one = "dex" if ability != "dex" else "con"
        self.builder_half_elf_bonus_two = ability

    def set_builder_score(self, ability: str, value: str) -> None:
        if ability not in ABILITY_KEYS:
            return
        score = _safe_int(value, _recommended_standard_array(self.builder_class)[ability], minimum=1, maximum=30)
        self.builder_scores = {**self.builder_scores, ability: str(score)}

    def go(self, view: str) -> None:
        if view != "auth" and not self.is_authenticated:
            self.current_view = "auth"
            self.auth_message = "Log in to see your characters and campaigns."
            return
        self.current_view = view

    def view_character(self, character_id: int) -> None:
        self.selected_character_id = int(character_id)

    def open_sheet(self, character_id: int) -> None:
        self.selected_character_id = int(character_id)
        self.current_view = "sheet"

    def _reset_builder(self) -> None:
        self.builder_mode = "create"
        self.editing_character_id = 0
        self.builder_name = ""
        self.builder_level = "1"
        self.builder_armor = "chain mail"
        self.builder_shield = True
        self.builder_skill_selection = ["Athletics", "Perception"]
        self.builder_skill_extra = ""
        self.builder_notes = ""
        self.builder_ancestry = "Human"
        self.builder_class = "Fighter"
        self.builder_background = "Soldier"
        self.builder_scores = {key: str(value) for key, value in _recommended_standard_array("Fighter").items()}
        self.builder_saves = CLASS_SAVE_PROFICIENCIES["Fighter"]
        self.builder_half_elf_bonus_one = "dex"
        self.builder_half_elf_bonus_two = "con"
        self.builder_form_nonce += 1

    def start_new_character(self) -> None:
        self._reset_builder()
        self.go("builder")

    def start_edit_character(self, character_id: int) -> None:
        """Open the builder pre-filled with an existing character."""
        character = next((c for c in self.characters if int(c["id"]) == int(character_id)), None)
        if character is None:
            self.app_message = "That character could not be found."
            return
        self.builder_mode = "edit"
        self.editing_character_id = int(character_id)
        self.builder_name = character["name"]
        self.builder_level = str(character["level"])
        self.builder_armor = character["armor"] if character["armor"] in ARMOR_CHOICES else "none"
        self.builder_shield = bool(character["shield"])
        known_skills: list[str] = []
        extra_skills: list[str] = []
        for part in str(character["skills"]).split(","):
            entry = part.strip()
            if not entry:
                continue
            label = SKILL_LABEL_BY_LOWER.get(entry.lower())
            if label and label not in known_skills:
                known_skills.append(label)
            elif not label:
                extra_skills.append(entry)
        self.builder_skill_selection = [name for name in SKILL_LABELS_ORDERED if name in known_skills]
        self.builder_skill_extra = ", ".join(extra_skills)
        self.builder_notes = character["notes"]
        self.builder_ancestry = character["ancestry"] if character["ancestry"] in ANCESTRY_OPTIONS else "Human"
        self.builder_class = character["character_class"] if character["character_class"] in CLASS_OPTIONS else "Fighter"
        self.builder_background = character["background"] if character["background"] in BACKGROUND_OPTIONS else "Soldier"
        # Stored scores already include ancestry bonuses, so edit mode treats
        # them as final values and never re-applies bonuses on save.
        self.builder_scores = {key: str(character[key]) for key in ABILITY_KEYS}
        self.builder_saves = character["saves"]
        self.builder_form_nonce += 1
        self.go("builder")

    def cancel_edit_character(self) -> None:
        self._reset_builder()
        self.go("sheet")

    def reset_builder_form(self) -> None:
        """Throw away unsaved builder changes (confirmed via dialog in the UI)."""
        if self.builder_mode == "edit" and self.editing_character_id:
            name = self.builder_name
            self.start_edit_character(self.editing_character_id)
            self.app_message = f"Restored {name}'s last saved values."
        else:
            self._reset_builder()
            self.app_message = "Builder reset to a fresh hero."

    def delete_character(self, character_id: int) -> None:
        character = next((c for c in self.characters if int(c["id"]) == int(character_id)), None)
        name = character["name"] if character else "That character"
        if not data_access.delete_character(int(character_id), self.user_id):
            self.app_message = "That character could not be deleted."
            return
        if self.selected_character_id == int(character_id):
            self.selected_character_id = 0
        if self.editing_character_id == int(character_id):
            self._reset_builder()
        self.load_user_data()
        self.app_message = f"{name} was deleted and removed from their campaigns."

    def create_character(self, form_data: dict[str, Any]) -> None:
        if not self.is_authenticated:
            self.go("auth")
            return
        editing = self.builder_mode == "edit" and self.editing_character_id
        ancestry = form_data.get("ancestry") or self.builder_ancestry
        character_class = form_data.get("character_class") or self.builder_class
        default_scores = _recommended_standard_array(character_class)
        base_scores = {
            key: _safe_int(
                form_data.get(key, self.builder_scores.get(key)),
                default_scores[key],
                minimum=1,
                maximum=30,
            )
            for key in ABILITY_KEYS
        }
        if editing:
            # Edit mode: entered scores are final (bonuses were applied at creation).
            scores = base_scores
        else:
            scores = _apply_ancestry_bonuses(
                ancestry,
                base_scores,
                self.builder_half_elf_bonus_one,
                self.builder_half_elf_bonus_two,
            )
        skill_entries = list(self.builder_skill_selection)
        if self.builder_skill_extra.strip():
            skill_entries.append(self.builder_skill_extra.strip())
        character = {
            "name": form_data.get("name", "Unnamed Hero").strip() or "Unnamed Hero",
            "ancestry": ancestry,
            "character_class": character_class,
            "background": form_data.get("background") or self.builder_background,
            "level": _safe_int(form_data.get("level"), 1, minimum=1, maximum=20),
            **scores,
            "armor": form_data.get("armor", "none"),
            "shield": form_data.get("shield", "off") == "on",
            "skills": ", ".join(skill_entries) or "Perception",
            "saves": form_data.get("saves") or self.builder_saves,
            "notes": form_data.get("notes", ""),
        }
        if editing:
            if not data_access.update_character(self.editing_character_id, self.user_id, character):
                self.app_message = "Saving changes failed — that character may have been deleted."
                return
            self.selected_character_id = self.editing_character_id
            self.app_message = f"{character['name']} was updated."
            self._reset_builder()
        else:
            character_id = data_access.create_character(self.user_id, character)
            self.selected_character_id = character_id
            self.app_message = f"{character['name']} was saved to {self.user_email}."
        self.load_user_data()
        self.current_view = "sheet"

    def create_campaign(self, form_data: dict[str, Any]) -> None:
        if not self.is_authenticated:
            self.go("auth")
            return
        name = form_data.get("name", "New Campaign").strip() or "New Campaign"
        code_seed = _invite_code_seed(name)
        invite_code = f"{code_seed}-{secrets.randbelow(9000) + 1000}"
        campaign_id = data_access.create_campaign(
            self.user_id,
            name,
            form_data.get("next_session", "Next session TBD"),
            invite_code,
        )
        self.load_user_data()
        self.select_campaign(campaign_id)
        self.campaign_tab = "dm"
        self.dm_tab = "status"
        self.current_view = "campaign"

    def join_campaign(self, form_data: dict[str, Any]) -> None:
        if not self.is_authenticated:
            self.go("auth")
            return
        code = form_data.get("invite_code", "").strip().upper()
        if not code:
            self.join_message = "Ask your DM for the campaign's invite code, then enter it here."
            return
        character_id = _choice_to_id(self.join_character_choice) or None
        initial_hp = self._character_starting_hp(character_id) if character_id else data_access.HP_UNSET
        ok, reason = data_access.join_campaign(self.user_id, code, character_id, initial_hp)
        if not ok:
            if reason == "character_not_owned":
                self.join_message = "That character does not belong to your account."
            else:
                self.join_message = "That invite code was not found. Double-check it with your DM."
            return
        if reason == "joined" and character_id:
            self.join_message = f"You joined with {self.join_character_choice}. Have fun!"
        elif reason == "joined":
            self.join_message = "Joined! Attach a character from the campaign page when you're ready."
        elif reason == "character_updated":
            self.join_message = "You were already in that campaign — your character was updated."
        else:
            self.join_message = "You are already in that campaign."
        self.campaign = _blank_campaign()  # force selection of the joined campaign below
        self.load_user_data()
        joined = data_access.find_campaign_by_invite(code)
        if joined:
            self.select_campaign(int(joined["id"]))
        self.campaign_tab = "hub"
        self.current_view = "campaign"

    def attach_character_to_campaign(self) -> None:
        """Attach or swap the chosen character on the currently open campaign."""
        campaign_id = int(self.campaign.get("id") or 0)
        character_id = _choice_to_id(self.assign_character_choice)
        if not campaign_id:
            self.app_message = "Open a campaign before attaching a character."
            return
        if not character_id:
            self.app_message = "Pick a character from the list first."
            return
        initial_hp = self._character_starting_hp(character_id)
        ok, reason = data_access.assign_character_to_campaign(campaign_id, self.user_id, character_id, initial_hp)
        if not ok:
            self.app_message = (
                "That character does not belong to your account."
                if reason == "character_not_owned"
                else "You are not a member of that campaign."
            )
            return
        self.app_message = f"{self.assign_character_choice} is now playing in {self.campaign['name']}."
        self.load_user_data()

    def save_shared_notes(self, value: str) -> None:
        campaign_id = int(self.campaign.get("id") or 0)
        if not campaign_id:
            return
        data_access.update_campaign_details(campaign_id, shared_notes=value)
        self.campaign = {**self.campaign, "shared_notes": value}

    def save_session_log(self, value: str) -> None:
        campaign_id = int(self.campaign.get("id") or 0)
        if not campaign_id or self.campaign.get("role") != "dm":
            return
        data_access.update_campaign_details(campaign_id, session_log=value)
        self.campaign = {**self.campaign, "session_log": value}

    def save_next_session(self, value: str) -> None:
        campaign_id = int(self.campaign.get("id") or 0)
        if not campaign_id or self.campaign.get("role") != "dm":
            return
        data_access.update_campaign_details(campaign_id, next_session=value)
        self.campaign = {**self.campaign, "next_session": value}

    def save_dm_notes(self, value: str) -> None:
        campaign_id = int(self.campaign.get("id") or 0)
        if not campaign_id or self.campaign.get("role") != "dm":
            return
        data_access.save_dm_notes(campaign_id, value)
        self.dm_notes = value

    def roll_dice(self, form_data: dict[str, Any]) -> None:
        die = _die_size(form_data.get("die"))
        count = _safe_int(form_data.get("count"), 1, minimum=1, maximum=20)
        modifier = _safe_int(form_data.get("modifier"), 0, minimum=-99, maximum=99)
        rolls = [random.randint(1, die) for _ in range(count)]
        total = sum(rolls) + modifier
        self.dice_result = f"{count}d{die} {format_bonus(modifier)}: {rolls} -> {total}"

    def damage_member(self, member_id: int, amount: int) -> None:
        self.members = [
            {**member, "current_hp": max(0, int(member["current_hp"]) - amount)}
            if member["id"] == member_id
            else member
            for member in self.members
        ]
        self._persist_member_hp(member_id)
        self._sync_initiative_from_members()

    def heal_member(self, member_id: int, amount: int) -> None:
        self.members = [
            {**member, "current_hp": min(int(member["max_hp"]), int(member["current_hp"]) + amount)}
            if member["id"] == member_id
            else member
            for member in self.members
        ]
        self._persist_member_hp(member_id)
        self._sync_initiative_from_members()

    def damage_combatant(self, combatant_key: str, amount: int) -> None:
        self.initiative = [
            {**row, "current_hp": max(0, int(row["current_hp"]) - amount)}
            if row["key"] == combatant_key
            else row
            for row in self.initiative
        ]
        self._persist_combatant_hp(combatant_key)
        self._sync_members_from_initiative()

    def heal_combatant(self, combatant_key: str, amount: int) -> None:
        self.initiative = [
            {**row, "current_hp": min(int(row["max_hp"]), int(row["current_hp"]) + amount)}
            if row["key"] == combatant_key
            else row
            for row in self.initiative
        ]
        self._persist_combatant_hp(combatant_key)
        self._sync_members_from_initiative()

    def next_turn(self) -> None:
        if self.initiative:
            self.current_turn = (self.current_turn + 1) % len(self.initiative)

    def add_npc(self, form_data: dict[str, Any]) -> None:
        if not self.campaign.get("id"):
            self.app_message = "Create or open a campaign before adding NPCs."
            return
        max_hp_value = _safe_int(form_data.get("max_hp"), 10, minimum=1, maximum=999)
        npc = {
            "name": form_data.get("name", "New NPC").strip() or "New NPC",
            "ac": _safe_int(form_data.get("ac"), 12, minimum=1, maximum=50),
            "current_hp": max_hp_value,
            "max_hp": max_hp_value,
            "stats": form_data.get("stats", "Key tactics and saves"),
        }
        data_access.create_npc(int(self.campaign["id"]), npc)
        self.select_campaign(int(self.campaign["id"]))

    def _character_starting_hp(self, character_id: int) -> int:
        for character in self.characters:
            if int(character["id"]) == character_id:
                return max_hp(character["character_class"], int(character["level"]), int(character["con"]))
        return data_access.HP_UNSET

    def _persist_member_hp(self, member_id: int) -> None:
        for member in self.members:
            if member["id"] == member_id:
                data_access.update_member_hp(member_id, int(member["current_hp"]))
                return

    def _persist_combatant_hp(self, combatant_key: str) -> None:
        for row in self.initiative:
            if row["key"] != combatant_key:
                continue
            if row.get("member_id"):
                data_access.update_member_hp(int(row["member_id"]), int(row["current_hp"]))
            elif row.get("npc_id"):
                data_access.update_npc_hp(int(row["npc_id"]), int(row["current_hp"]))
            return

    def _member_view(self, row: dict[str, Any]) -> dict[str, Any]:
        character_name = row.get("character") or f"{row['display_name']} (no character)"
        class_level = "DM" if not row.get("character_class") else f"{row['character_class']} {row['level']}"
        max_hp_value = (
            max_hp(row["character_class"], int(row["level"]), int(row["constitution"]))
            if row.get("character_class")
            else 0
        )
        stored_hp = int(row["current_hp"])
        if stored_hp < 0:
            current_hp = max_hp_value
        else:
            current_hp = min(stored_hp, max_hp_value) if max_hp_value > 0 else 0
        hp_state = _hp_state(current_hp, max_hp_value)
        return {
            "id": row["id"],
            "user_id": row.get("user_id", 0),
            "character": character_name,
            "class_level": class_level,
            "current_hp": current_hp,
            "max_hp": max_hp_value,
            "hp_percent": _hp_percent(current_hp, max_hp_value),
            "hp_state": hp_state,
            "location": row["location"],
            "conditions": row["active_conditions"],
            "role": row["role"],
        }

    def _npc_view(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "ac": row["armor_class"],
            "current_hp": row["current_hp"],
            "max_hp": row["max_hp"],
            "stats": row["key_stats"],
        }

    def _initiative_from_campaign(self) -> list[dict[str, Any]]:
        combatants = [
            {
                "key": f"member:{member['id']}",
                "name": member["character"],
                "type": "pc" if member["role"] == "player" else "dm",
                "ac": 10,
                "current_hp": member["current_hp"],
                "max_hp": member["max_hp"],
                "initiative": 10,
                "member_id": member["id"],
                "npc_id": 0,
            }
            for member in self.members
            if member["max_hp"] > 0
        ]
        combatants.extend(
            {
                "key": f"npc:{npc['id']}",
                "name": npc["name"],
                "type": "npc",
                "ac": npc["ac"],
                "current_hp": npc["current_hp"],
                "max_hp": npc["max_hp"],
                "initiative": 8,
                "member_id": 0,
                "npc_id": npc["id"],
            }
            for npc in self.npcs
        )
        return combatants

    def _sync_members_from_initiative(self) -> None:
        hp_by_member_id = {
            int(row["member_id"]): row["current_hp"]
            for row in self.initiative
            if int(row.get("member_id") or 0) > 0
        }
        self.members = [
            {
                **member,
                "current_hp": hp_by_member_id.get(int(member["id"]), member["current_hp"]),
                "hp_percent": _hp_percent(
                    hp_by_member_id.get(int(member["id"]), member["current_hp"]),
                    int(member["max_hp"]),
                ),
                "hp_state": _hp_state(
                    hp_by_member_id.get(int(member["id"]), member["current_hp"]),
                    int(member["max_hp"]),
                ),
            }
            for member in self.members
        ]

    def _sync_initiative_from_members(self) -> None:
        hp_by_member_id = {int(row["id"]): row["current_hp"] for row in self.members}
        self.initiative = [
            {
                **row,
                "current_hp": hp_by_member_id.get(int(row.get("member_id") or 0), row["current_hp"]),
            }
            for row in self.initiative
        ]

    @rx.var
    def is_builder_editing(self) -> bool:
        return self.builder_mode == "edit"

    @rx.var
    def builder_form_key(self) -> str:
        """Remounts prefilled builder inputs when switching targets or resetting."""
        return f"{self.builder_mode}-{self.editing_character_id}-{self.builder_form_nonce}"

    @rx.var
    def builder_score_rows(self) -> list[dict[str, Any]]:
        bonuses = _ability_bonuses_for_ancestry(
            self.builder_ancestry,
            self.builder_half_elf_bonus_one,
            self.builder_half_elf_bonus_two,
        )
        recommended = _recommended_standard_array(self.builder_class)
        rows = []
        for key in ABILITY_KEYS:
            base = _safe_int(self.builder_scores.get(key), recommended[key], minimum=1, maximum=30)
            bonus = bonuses[key]
            rows.append(
                {
                    "key": key,
                    "label": key.upper(),
                    "full_label": ABILITY_LABELS[key],
                    "base": base,
                    "bonus": _format_ability_bonus(bonus),
                    "total": max(1, min(30, base + bonus)),
                }
            )
        return rows

    @rx.var
    def builder_bonus_labels(self) -> dict[str, str]:
        bonuses = _ability_bonuses_for_ancestry(
            self.builder_ancestry,
            self.builder_half_elf_bonus_one,
            self.builder_half_elf_bonus_two,
        )
        return {key: _format_ability_bonus(bonuses[key]) for key in ABILITY_KEYS}

    @rx.var
    def builder_final_scores(self) -> dict[str, int]:
        base_scores = {
            key: _safe_int(
                self.builder_scores.get(key),
                _recommended_standard_array(self.builder_class)[key],
                minimum=1,
                maximum=30,
            )
            for key in ABILITY_KEYS
        }
        if self.builder_mode == "edit":
            # Stored scores already include ancestry bonuses.
            return base_scores
        return _apply_ancestry_bonuses(
            self.builder_ancestry,
            base_scores,
            self.builder_half_elf_bonus_one,
            self.builder_half_elf_bonus_two,
        )

    @rx.var
    def builder_proficiency_bonus(self) -> int:
        return proficiency_bonus(_safe_int(self.builder_level, 1, minimum=1, maximum=20))

    @rx.var
    def builder_skill_rows(self) -> list[dict[str, Any]]:
        """One row per SRD skill with its live bonus, for the proficiency picker."""
        scores = self.builder_final_scores
        prof = self.builder_proficiency_bonus
        rows = []
        for label in SKILL_LABELS_ORDERED:
            ability = SKILL_ABILITY_BY_LABEL[label]
            modifier = ability_modifier(scores[ability])
            selected = label in self.builder_skill_selection
            bonus = modifier + (prof if selected else 0)
            detail = (
                f"{ability.upper()} · proficient (+{prof} included)"
                if selected
                else f"{ability.upper()} · pick to add +{prof}"
            )
            rows.append(
                {
                    "label": label,
                    "selected": selected,
                    "bonus": format_bonus(bonus),
                    "detail": detail,
                }
            )
        return rows

    @rx.var
    def builder_skills_summary(self) -> str:
        count = len(self.builder_skill_selection)
        if count == 0:
            return "No skills picked yet — most characters start with 4 (2 from class, 2 from background)."
        return f"{count} picked: " + ", ".join(self.builder_skill_selection)

    @rx.var
    def builder_save_rows(self) -> list[dict[str, str]]:
        """The class's saving-throw proficiencies with their live bonuses."""
        scores = self.builder_final_scores
        prof = self.builder_proficiency_bonus
        rows = []
        for part in self.builder_saves.split(","):
            label = part.strip()
            ability = ABILITY_KEYS_BY_LABEL.get(label)
            bonus = format_bonus(ability_modifier(scores[ability]) + prof) if ability else ""
            rows.append({"label": label, "bonus": bonus})
        return rows

    @rx.var
    def builder_armor_text(self) -> str:
        armor = ARMOR.get(self.builder_armor, ARMOR["none"])
        if armor.category == "heavy":
            dex_part = "your DEX bonus does not apply"
        elif armor.dex_cap is None:
            dex_part = "adds your full DEX bonus"
        else:
            dex_part = f"adds DEX up to +{armor.dex_cap}"
        stealth_part = ", disadvantage on Stealth" if armor.stealth_disadvantage else ""
        return f"{armor.name}: base AC {armor.base_ac}, {dex_part}{stealth_part}."

    @rx.var
    def builder_ac_text(self) -> str:
        scores = self.builder_final_scores
        ac = armor_class(scores["dex"], self.builder_armor, self.builder_shield)
        shield_part = " (includes +2 from shield)" if self.builder_shield else ""
        return f"Armor class with these choices: {ac}{shield_part}"

    @rx.var
    def ancestry_bonus_text(self) -> str:
        bonuses = _ability_bonuses_for_ancestry(
            self.builder_ancestry,
            self.builder_half_elf_bonus_one,
            self.builder_half_elf_bonus_two,
        )
        parts = [f"{_format_ability_bonus(value)} {key.upper()}" for key, value in bonuses.items() if value]
        return ", ".join(parts) if parts else "No ability score bonus"

    @rx.var
    def class_array_text(self) -> str:
        recommended = _recommended_standard_array(self.builder_class)
        return ", ".join(f"{key.upper()} {recommended[key]}" for key in ABILITY_KEYS)

    @rx.var
    def background_bonus_text(self) -> str:
        return "No ability score change in this 5e ruleset"

    @rx.var
    def half_elf_bonus_one_label(self) -> str:
        return ABILITY_LABELS[self.builder_half_elf_bonus_one]

    @rx.var
    def half_elf_bonus_two_label(self) -> str:
        return ABILITY_LABELS[self.builder_half_elf_bonus_two]

    @rx.var
    def has_characters(self) -> bool:
        return len(self.characters) > 0

    @rx.var
    def has_campaigns(self) -> bool:
        return len(self.campaigns) > 0

    @rx.var
    def has_active_campaign(self) -> bool:
        return bool(self.campaign.get("id"))

    @rx.var
    def is_campaign_dm(self) -> bool:
        return self.campaign.get("role") == "dm"

    @rx.var
    def has_campaign_character(self) -> bool:
        return bool(self.campaign.get("my_character_id"))

    @rx.var
    def character_choices(self) -> list[str]:
        """Dropdown labels for the user's characters, e.g. "Thorin (#3)"."""
        return [f"{character['name']} (#{character['id']})" for character in self.characters]

    @rx.var
    def party_members(self) -> list[dict[str, Any]]:
        return [member for member in self.members if int(member["max_hp"]) > 0]

    @rx.var
    def effective_character_id(self) -> int:
        ids = [int(character["id"]) for character in self.characters]
        if self.selected_character_id in ids:
            return self.selected_character_id
        return ids[0] if ids else 0

    @rx.var
    def primary_character(self) -> dict[str, Any]:
        target_id = self.effective_character_id
        for character in self.characters:
            if int(character["id"]) == target_id:
                return character
        return {
            "id": 0,
            "name": "No character yet",
            "ancestry": "",
            "character_class": "",
            "background": "",
            "level": 1,
            "str": 10,
            "dex": 10,
            "con": 10,
            "int": 10,
            "wis": 10,
            "cha": 10,
            "armor": "none",
            "shield": False,
            "skills": "",
            "saves": "",
            "notes": "",
            "campaign_names": "",
        }

    @rx.var
    def primary_stats(self) -> dict[str, Any]:
        character = self.primary_character
        scores = {
            "str": character["str"],
            "dex": character["dex"],
            "con": character["con"],
            "int": character["int"],
            "wis": character["wis"],
            "cha": character["cha"],
        }
        klass = character["character_class"] or "fighter"
        level = int(character["level"])
        hp = max_hp(klass, level, scores["con"])
        ac = armor_class(scores["dex"], character["armor"], character["shield"])
        return {
            "hp": hp,
            "ac": ac,
            "proficiency": format_bonus(proficiency_bonus(level)),
            "initiative": format_bonus((scores["dex"] - 10) // 2),
            "spell_dc": spell_save_dc(klass, level, scores),
            "spell_attack": format_bonus(spell_attack_bonus(klass, level, scores)),
            "perception": format_bonus(skill_bonus(scores["wis"], level, proficient=True)),
            "stealth": format_bonus(skill_bonus(scores["dex"], level, proficient=False)),
        }

    @rx.var
    def party_summary(self) -> str:
        active = len(self.party_members)
        hurt = len([m for m in self.party_members if _hp_state(m["current_hp"], m["max_hp"]) != "healthy"])
        return f"{active} characters, {hurt} need attention"
