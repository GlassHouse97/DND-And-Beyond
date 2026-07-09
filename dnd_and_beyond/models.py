"""Database table declarations for the Reflex app."""

from __future__ import annotations

import reflex as rx
from sqlmodel import Field


class User(rx.Model, table=True):
    email: str = Field(index=True, unique=True)
    password_hash: str
    display_name: str


class Character(rx.Model, table=True):
    owner_user_id: int = Field(index=True)
    name: str
    ancestry: str
    character_class: str
    background: str
    level: int = 1
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    armor_name: str = "none"
    has_shield: bool = False
    skill_proficiencies: str = ""
    save_proficiencies: str = ""
    weapons: str = ""
    spells: str = ""
    notes: str = ""


class Campaign(rx.Model, table=True):
    host_user_id: int = Field(index=True)
    name: str
    invite_code: str = Field(index=True, unique=True)
    next_session: str = ""
    session_log: str = ""
    shared_notes: str = ""


class CampaignMember(rx.Model, table=True):
    campaign_id: int = Field(index=True)
    user_id: int = Field(index=True)
    character_id: int | None = Field(default=None, index=True)
    role: str = "player"
    # -1 means "HP not initialized yet" (see data_access.HP_UNSET); a real 0 is down/dying.
    current_hp: int = -1
    location: str = "Camp"
    active_conditions: str = ""


class DMNote(rx.Model, table=True):
    campaign_id: int = Field(index=True)
    title: str
    body: str


class NPC(rx.Model, table=True):
    campaign_id: int = Field(index=True)
    name: str
    armor_class: int = 10
    current_hp: int = 1
    max_hp: int = 1
    key_stats: str = ""


class InitiativeCombatant(rx.Model, table=True):
    campaign_id: int = Field(index=True)
    source_type: str = "pc"
    source_id: int | None = None
    name: str
    armor_class: int = 10
    current_hp: int = 1
    max_hp: int = 1
    initiative: int = 0
    turn_order: int = 0


class RulesRace(rx.Model, table=True):
    index: str = Field(index=True, unique=True)
    name: str
    source: str = "dnd5eapi.co"
    payload_json: str


class RulesClass(rx.Model, table=True):
    index: str = Field(index=True, unique=True)
    name: str
    hit_die: int = 8
    source: str = "dnd5eapi.co"
    payload_json: str


class RulesBackground(rx.Model, table=True):
    index: str = Field(index=True, unique=True)
    name: str
    source: str = "dnd5eapi.co"
    payload_json: str


class RulesSpell(rx.Model, table=True):
    index: str = Field(index=True, unique=True)
    name: str
    level: int = 0
    source: str = "dnd5eapi.co"
    payload_json: str


class RulesEquipment(rx.Model, table=True):
    index: str = Field(index=True, unique=True)
    name: str
    equipment_category: str = ""
    source: str = "dnd5eapi.co"
    payload_json: str


class RulesCondition(rx.Model, table=True):
    index: str = Field(index=True, unique=True)
    name: str
    source: str = "dnd5eapi.co"
    payload_json: str

