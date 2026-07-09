"""Main Reflex UI for DND and Beyond."""

from __future__ import annotations

from typing import Any

import reflex as rx

from dnd_and_beyond.state import (
    ABILITY_LABELS,
    ANCESTRY_OPTIONS,
    BACKGROUND_OPTIONS,
    CLASS_OPTIONS,
    AppState,
)


def icon_button(icon: str, label: str, on_click=None, class_name: str = "icon-button") -> rx.Component:
    return rx.button(rx.icon(icon, size=18), rx.text(label, class_name="sr-only"), on_click=on_click, class_name=class_name)


def stat_tile(label: str, value: Any, sublabel: str = "") -> rx.Component:
    return rx.box(
        rx.text(label, class_name="stat-label"),
        rx.heading(value, class_name="stat-value"),
        rx.cond(sublabel != "", rx.text(sublabel, class_name="stat-sub"), rx.fragment()),
        class_name="stat-tile",
    )


def splash() -> rx.Component:
    """Shown while the client is (re)connecting, instead of flashing stale views."""
    return rx.vstack(
        rx.box("D20", class_name="brand-mark"),
        rx.spinner(size="3"),
        rx.text("Gathering the party...", class_name="body-text"),
        spacing="3",
        align="center",
        justify="center",
        min_height="50vh",
    )


def shell(content: rx.Component) -> rx.Component:
    return rx.box(
        rx.box(
            rx.hstack(
                rx.hstack(
                    rx.box("D20", class_name="brand-mark"),
                    rx.vstack(
                        rx.heading("DND and Beyond", class_name="brand-title"),
                        rx.text("5e character and campaign command center", class_name="brand-subtitle"),
                        spacing="0",
                        align="start",
                    ),
                    spacing="3",
                    align="center",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.button("Dashboard", on_click=lambda: AppState.go("dashboard"), class_name="nav-button"),
                    rx.button("Builder", on_click=lambda: AppState.go("builder"), class_name="nav-button"),
                    rx.button("Sheet", on_click=lambda: AppState.go("sheet"), class_name="nav-button"),
                    rx.button("Campaign", on_click=lambda: AppState.go("campaign"), class_name="nav-button"),
                    rx.cond(
                        AppState.is_hydrated,
                        rx.cond(
                            AppState.is_authenticated,
                            icon_button("log-out", "Sign out", AppState.logout),
                            rx.button("Sign in", on_click=lambda: AppState.go("auth"), class_name="primary-small"),
                        ),
                        rx.fragment(),
                    ),
                    spacing="2",
                    align="center",
                    class_name="nav-actions",
                ),
                width="100%",
                align="center",
            ),
            class_name="topbar",
        ),
        # Until hydration (initial load or reconnect) completes, state holds
        # placeholder defaults — rendering them causes login-screen flashes.
        rx.box(rx.cond(AppState.is_hydrated, content, splash()), class_name="page-shell"),
        footer(),
        class_name="app-bg",
    )


def footer() -> rx.Component:
    return rx.box(
        rx.text(
            "Rules data sourced from the 5.1 SRD via dnd5eapi.co and redistributed under CC-BY-4.0. "
            "This fan tool uses no Wizards of the Coast logos or proprietary trade dress.",
            class_name="footer-text",
        ),
        class_name="footer",
    )


def auth_panel() -> rx.Component:
    return shell(
        rx.grid(
            rx.box(
                rx.text("ACCOUNT", class_name="eyebrow"),
                rx.heading("Your table, your account.", class_name="page-title"),
                rx.text(
                    "Characters and campaigns are saved to the verified email you use to log in.",
                    class_name="lead",
                ),
                rx.hstack(
                    rx.button("Login", on_click=AppState.set_auth_mode("login"), class_name=rx.cond(AppState.auth_mode == "login", "tab active", "tab")),
                    rx.button("Register", on_click=AppState.set_auth_mode("register"), class_name=rx.cond(AppState.auth_mode == "register", "tab active", "tab")),
                    rx.button("Verify Email", on_click=AppState.set_auth_mode("verify"), class_name=rx.cond(AppState.auth_mode == "verify", "tab active", "tab")),
                    class_name="segmented",
                ),
                rx.form(
                    rx.vstack(
                        rx.cond(
                            AppState.auth_mode == "register",
                            rx.input(name="display_name", placeholder="Display name", class_name="field"),
                            rx.fragment(),
                        ),
                        rx.input(name="email", placeholder="Email address", type="email", class_name="field"),
                        rx.cond(
                            AppState.auth_mode == "verify",
                            rx.input(name="verification_token", placeholder="Verification code", class_name="field"),
                            rx.input(name="password", placeholder="Password", type="password", class_name="field"),
                        ),
                        rx.button(rx.icon("key-round", size=18), rx.text("Continue"), type="submit", class_name="primary-action"),
                        rx.text(AppState.auth_message, class_name="form-note"),
                        spacing="3",
                    ),
                    on_submit=AppState.auth_submit,
                    auto_complete="off",
                    reset_on_submit=True,
                ),
                class_name="panel strong-panel",
            ),
            rx.box(
                rx.text("LOCAL TEST MODE", class_name="eyebrow"),
                rx.heading("Blank by default. Personal once verified.", class_name="hero-heading"),
                rx.text("Registration writes a verification message to the local dev outbox until SMTP is configured for hosting.", class_name="lead"),
                rx.grid(
                    stat_tile("Data", "Blank", "per account"),
                    stat_tile("Login", "Email", "verification"),
                    stat_tile("Roles", "DM/Player", "per campaign"),
                    columns="3",
                    spacing="3",
                    class_name="hero-stats",
                ),
                class_name="hero-panel",
            ),
            columns="2",
            spacing="5",
            class_name="two-col auth-grid",
        )
    )


def dashboard() -> rx.Component:
    return shell(
        rx.vstack(
            rx.box(
                rx.text("DASHBOARD", class_name="eyebrow"),
                rx.heading("Welcome back, ", rx.text(AppState.display_name, as_="span", class_name="accent-text"), class_name="page-title"),
                rx.text(AppState.user_email, class_name="lead"),
                rx.text(AppState.app_message, class_name="form-note"),
                class_name="page-intro",
            ),
            rx.grid(
                action_card("Create Character", "Build a 5e-compatible character with calculated AC, HP, proficiency, saves, skills, and spell math.", "wand-sparkles", "builder", on_open=AppState.start_new_character),
                action_card("Open Sheet", "A phone-friendly, at-the-table character sheet with core stats pinned at the top.", "scroll-text", "sheet"),
                action_card("Campaign Hub", "Shared notes, roster HP, dice rolling, and DM-only tools for where you last left off.", "map", "campaign"),
                columns="3",
                spacing="4",
                class_name="action-grid",
            ),
            rx.grid(
                rx.box(
                    rx.text("MY CHARACTERS", class_name="eyebrow"),
                    rx.cond(
                        AppState.has_characters,
                        rx.vstack(rx.foreach(AppState.characters, character_dashboard_row), spacing="2"),
                        empty_state("No characters yet", "Create your first character and it will stay attached to this email login."),
                    ),
                    class_name="panel",
                ),
                rx.box(
                    rx.text("MY CAMPAIGNS", class_name="eyebrow"),
                    rx.cond(
                        AppState.has_campaigns,
                        rx.vstack(rx.foreach(AppState.campaigns, campaign_dashboard_row), spacing="2"),
                        empty_state("No campaigns yet", "Host a campaign or join a friend's invite code."),
                    ),
                    class_name="panel",
                ),
                columns="2",
                spacing="4",
                class_name="two-col",
            ),
            rx.grid(host_campaign_panel(), join_campaign_panel(), columns="2", spacing="4", class_name="two-col"),
            spacing="5",
        )
    )


def action_card(title: str, body: str, icon: str, view: str, on_open=None) -> rx.Component:
    return rx.box(
        rx.hstack(rx.box(rx.icon(icon, size=24), class_name="card-icon"), rx.heading(title, class_name="card-title"), align="center", spacing="3"),
        rx.text(body, class_name="body-text"),
        rx.button(rx.text("Open"), rx.icon("arrow-right", size=18), on_click=on_open or (lambda: AppState.go(view)), class_name="secondary-action"),
        class_name="action-card",
    )


def compact_member_row(member: rx.Var[dict]) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(member["character"], class_name="row-title"),
            rx.text(member["class_level"], class_name="row-subtitle"),
            spacing="0",
            align="start",
        ),
        rx.spacer(),
        rx.text(member["current_hp"], "/", member["max_hp"], class_name="hp-pill"),
        class_name="compact-row",
    )


def empty_state(title: str, body: str) -> rx.Component:
    return rx.box(
        rx.box(rx.icon("sparkles", size=24), class_name="card-icon"),
        rx.heading(title, class_name="mini-heading"),
        rx.text(body, class_name="body-text"),
        class_name="empty-state",
    )


def character_dashboard_row(character: rx.Var[dict]) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(character["name"], class_name="row-title"),
            rx.text(character["character_class"], " ", character["level"], " / ", character["ancestry"], class_name="row-subtitle"),
            rx.cond(
                character["campaign_names"] != "",
                rx.text("Campaign: ", character["campaign_names"], class_name="row-subtitle"),
                rx.text("Not attached to a campaign", class_name="row-subtitle"),
            ),
            spacing="0",
            align="start",
        ),
        rx.spacer(),
        rx.button("Edit", on_click=lambda: AppState.start_edit_character(character["id"]), class_name="secondary-action"),
        rx.button("Sheet", on_click=lambda: AppState.open_sheet(character["id"]), class_name="secondary-action"),
        class_name="compact-row",
    )


def campaign_dashboard_row(campaign: rx.Var[dict]) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(campaign["name"], class_name="row-title"),
            rx.text("Role: ", campaign["role"], class_name="row-subtitle"),
            rx.cond(
                campaign["character_name"] != "",
                rx.text("Character: ", campaign["character_name"], class_name="row-subtitle"),
                rx.text("No character attached yet — open the campaign to pick one", class_name="row-subtitle"),
            ),
            spacing="0",
            align="start",
        ),
        rx.spacer(),
        rx.button("Open", on_click=lambda: AppState.open_campaign(campaign["id"]), class_name="secondary-action"),
        class_name="compact-row",
    )


def host_campaign_panel() -> rx.Component:
    return rx.box(
        rx.heading("Host a Campaign", class_name="section-heading"),
        rx.form(
            rx.vstack(
                rx.input(name="name", placeholder="Campaign name", class_name="field"),
                rx.input(name="next_session", placeholder="Next session", class_name="field"),
                rx.button("Create Campaign", type="submit", class_name="primary-action"),
                spacing="3",
            ),
            on_submit=AppState.create_campaign,
            reset_on_submit=True,
        ),
        class_name="panel",
    )


def join_campaign_panel() -> rx.Component:
    return rx.box(
        rx.heading("Join a Campaign", class_name="section-heading"),
        rx.vstack(
            rx.text("1. Get the invite code from your DM (they can copy it from their campaign page).", class_name="hint"),
            rx.text("2. Pick which character you're bringing — or skip it and attach one later.", class_name="hint"),
            rx.text("3. Join, and the campaign hub opens with the party roster and shared notes.", class_name="hint"),
            spacing="1",
            align="start",
        ),
        rx.form(
            rx.vstack(
                rx.input(name="invite_code", placeholder="Invite code, e.g. DRAGON-4271", class_name="field"),
                rx.cond(
                    AppState.has_characters,
                    rx.select(
                        AppState.character_choices,
                        placeholder="Choose a character (optional)",
                        on_change=AppState.set_join_character_choice,
                        class_name="field",
                    ),
                    rx.text("No characters yet — you can still join now and attach one after you build it.", class_name="hint"),
                ),
                rx.button("Join Campaign", type="submit", class_name="primary-action"),
                rx.text(AppState.join_message, class_name="form-note"),
                spacing="3",
            ),
            on_submit=AppState.join_campaign,
            reset_on_submit=False,
        ),
        class_name="panel",
    )


def reset_builder_dialog() -> rx.Component:
    """Reset All button that confirms before discarding unsaved builder changes."""
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            rx.button(
                rx.icon("rotate-ccw", size=16),
                rx.text("Reset All"),
                type="button",
                class_name="icon-button danger",
            ),
        ),
        rx.alert_dialog.content(
            rx.alert_dialog.title("Reset all builder changes?"),
            rx.alert_dialog.description(
                rx.cond(
                    AppState.is_builder_editing,
                    rx.text(
                        "This restores ",
                        AppState.builder_name,
                        "'s last saved values. Everything you changed since opening the editor will be lost.",
                    ),
                    rx.text(
                        "This clears every choice — name, race, class, scores, skills, armor, and notes — "
                        "back to a fresh default hero.",
                    ),
                ),
            ),
            rx.flex(
                rx.alert_dialog.cancel(rx.button("Keep my changes", class_name="secondary-action")),
                rx.alert_dialog.action(
                    rx.button(
                        "Reset all",
                        on_click=AppState.reset_builder_form,
                        class_name="icon-button danger",
                    ),
                ),
                spacing="3",
                justify="end",
                margin_top="16px",
            ),
        ),
    )


def character_builder() -> rx.Component:
    return shell(
        rx.vstack(
            rx.box(
                rx.text("CHARACTER BUILDER", class_name="eyebrow"),
                rx.cond(
                    AppState.is_builder_editing,
                    rx.heading("Editing ", AppState.builder_name, class_name="page-title"),
                    rx.heading("Create a table-ready hero.", class_name="page-title"),
                ),
                rx.cond(
                    AppState.is_builder_editing,
                    rx.text("Change anything and save — campaigns keep this character attached. Ability scores here are final values (race bonuses are already baked in).", class_name="lead"),
                    rx.text("This wizard starts with SRD-safe choices and immediately sends the result to a calculated sheet.", class_name="lead"),
                ),
                class_name="page-intro",
            ),
            rx.form(
                rx.grid(
                    builder_section(
                        "Identity",
                        labeled_field(
                            "Name",
                            rx.input(
                                name="name",
                                placeholder="Character name",
                                default_value=AppState.builder_name,
                                key=AppState.builder_form_key + "-name",
                                class_name="field",
                            ),
                        ),
                        labeled_field(
                            "Race",
                            rx.select(
                                list(ANCESTRY_OPTIONS),
                                name="ancestry",
                                default_value=AppState.builder_ancestry,
                                key=AppState.builder_form_key + "-ancestry",
                                on_change=AppState.set_builder_ancestry,
                                class_name="field",
                            ),
                            rx.cond(AppState.is_builder_editing, "", AppState.ancestry_bonus_text),
                        ),
                        rx.cond(
                            (AppState.builder_ancestry == "Half-Elf") & ~AppState.is_builder_editing,
                            rx.grid(
                                labeled_field(
                                    "Half-Elf +1",
                                    rx.select(
                                        [
                                            ABILITY_LABELS["str"],
                                            ABILITY_LABELS["dex"],
                                            ABILITY_LABELS["con"],
                                            ABILITY_LABELS["int"],
                                            ABILITY_LABELS["wis"],
                                        ],
                                        default_value=AppState.half_elf_bonus_one_label,
                                        on_change=AppState.set_half_elf_bonus_one,
                                        class_name="field",
                                    ),
                                ),
                                labeled_field(
                                    "Half-Elf +1",
                                    rx.select(
                                        [
                                            ABILITY_LABELS["str"],
                                            ABILITY_LABELS["dex"],
                                            ABILITY_LABELS["con"],
                                            ABILITY_LABELS["int"],
                                            ABILITY_LABELS["wis"],
                                        ],
                                        default_value=AppState.half_elf_bonus_two_label,
                                        on_change=AppState.set_half_elf_bonus_two,
                                        class_name="field",
                                    ),
                                ),
                                columns="2",
                                spacing="3",
                            ),
                            rx.fragment(),
                        ),
                        labeled_field(
                            "Class",
                            rx.select(
                                list(CLASS_OPTIONS),
                                name="character_class",
                                default_value=AppState.builder_class,
                                key=AppState.builder_form_key + "-class",
                                on_change=AppState.set_builder_class,
                                class_name="field",
                            ),
                            rx.cond(AppState.is_builder_editing, "", AppState.class_array_text),
                        ),
                        labeled_field(
                            "Background",
                            rx.select(
                                list(BACKGROUND_OPTIONS),
                                name="background",
                                default_value=AppState.builder_background,
                                key=AppState.builder_form_key + "-background",
                                on_change=AppState.set_builder_background,
                                class_name="field",
                            ),
                            AppState.background_bonus_text,
                        ),
                        labeled_field(
                            "Level",
                            rx.input(
                                name="level",
                                placeholder="Level",
                                default_value=AppState.builder_level,
                                on_blur=AppState.set_builder_level,
                                key=AppState.builder_form_key + "-level",
                                class_name="field",
                            ),
                        ),
                    ),
                    builder_section(
                        "Ability Scores",
                        score_grid(),
                        rx.cond(
                            AppState.is_builder_editing,
                            rx.text("These are the character's final scores — edit them directly (race bonuses were applied when the character was created).", class_name="hint"),
                            rx.text("Class chooses the standard-array order. Race bonuses are added to the final score shown on each tile.", class_name="hint"),
                        ),
                        rx.cond(
                            AppState.is_builder_editing,
                            rx.fragment(),
                            rx.grid(rx.foreach(AppState.builder_score_rows, score_summary_row), columns="1", spacing="2", class_name="score-summary-grid"),
                        ),
                    ),
                    builder_section(
                        "Equipment & Proficiencies",
                        labeled_field(
                            "Armor",
                            rx.select(
                                ["none", "leather", "studded leather", "scale mail", "half plate", "chain mail", "plate"],
                                name="armor",
                                default_value=AppState.builder_armor,
                                on_change=AppState.set_builder_armor,
                                key=AppState.builder_form_key + "-armor",
                                class_name="field",
                            ),
                            AppState.builder_armor_text,
                        ),
                        rx.checkbox(
                            "Shield equipped (+2 AC)",
                            name="shield",
                            default_checked=AppState.builder_shield,
                            on_change=AppState.set_builder_shield,
                            key=AppState.builder_form_key + "-shield",
                            class_name="check",
                        ),
                        rx.text(AppState.builder_ac_text, class_name="ac-preview"),
                        rx.text("Skill Proficiencies", class_name="field-label"),
                        rx.text(
                            "Tap the skills your class and background grant — proficiency adds your proficiency bonus to those checks.",
                            class_name="hint",
                        ),
                        rx.box(rx.foreach(AppState.builder_skill_rows, skill_chip), class_name="skill-grid"),
                        rx.text(AppState.builder_skills_summary, class_name="field-hint"),
                        rx.text("Saving Throws", class_name="field-label"),
                        rx.hstack(rx.foreach(AppState.builder_save_rows, save_chip), spacing="2", wrap="wrap"),
                        rx.text("Chosen automatically by your class.", class_name="hint"),
                        rx.text_area(
                            name="notes",
                            placeholder="Character notes",
                            default_value=AppState.builder_notes,
                            key=AppState.builder_form_key + "-notes",
                            class_name="textarea",
                        ),
                    ),
                    columns="3",
                    spacing="4",
                    class_name="builder-grid",
                ),
                rx.hstack(
                    rx.button(
                        rx.icon("sparkles", size=18),
                        rx.cond(AppState.is_builder_editing, rx.text("Save Changes"), rx.text("Create Character")),
                        type="submit",
                        class_name="primary-action",
                    ),
                    rx.cond(
                        AppState.is_builder_editing,
                        rx.button("Cancel Edit", on_click=AppState.cancel_edit_character, type="button", class_name="secondary-action"),
                        rx.button("Open Existing Sheet", on_click=lambda: AppState.go("sheet"), type="button", class_name="secondary-action"),
                    ),
                    reset_builder_dialog(),
                    class_name="form-actions",
                ),
                on_submit=AppState.create_character,
                reset_on_submit=False,
            ),
            spacing="5",
        )
    )


def builder_section(title: str, *children: rx.Component) -> rx.Component:
    return rx.box(rx.heading(title, class_name="section-heading"), rx.vstack(*children, spacing="3", align="stretch"), class_name="panel")


def labeled_field(label: str, control: rx.Component, hint: Any = "") -> rx.Component:
    return rx.vstack(
        rx.text(label, class_name="field-label"),
        control,
        rx.cond(hint != "", rx.text(hint, class_name="field-hint"), rx.fragment()),
        spacing="1",
        align="stretch",
        class_name="field-group",
    )


def score_grid() -> rx.Component:
    # Two columns: three squeezes the labels and race/final row off the tile.
    return rx.grid(
        score_input("STR", "str"),
        score_input("DEX", "dex"),
        score_input("CON", "con"),
        score_input("INT", "int"),
        score_input("WIS", "wis"),
        score_input("CHA", "cha"),
        columns="2",
        spacing="3",
    )


def skill_chip(row: rx.Var[dict]) -> rx.Component:
    """Toggleable skill proficiency with its live bonus and what picking it does."""
    return rx.button(
        rx.hstack(
            rx.vstack(
                rx.text(row["label"], class_name="skill-name"),
                rx.text(row["detail"], class_name="skill-detail"),
                spacing="0",
                align="start",
                min_width="0",
            ),
            rx.spacer(),
            rx.text(row["bonus"], class_name=rx.cond(row["selected"], "bonus-pill on", "bonus-pill")),
            width="100%",
            align="center",
            min_width="0",
        ),
        type="button",
        on_click=lambda: AppState.toggle_builder_skill(row["label"]),
        class_name=rx.cond(row["selected"], "skill-chip active", "skill-chip"),
    )


def save_chip(row: rx.Var[dict]) -> rx.Component:
    return rx.hstack(
        rx.text(row["label"], class_name="skill-name"),
        rx.text(row["bonus"], class_name="bonus-pill on"),
        spacing="2",
        align="center",
        class_name="save-chip",
    )


def score_input(label: str, name: str) -> rx.Component:
    return rx.box(
        rx.hstack(rx.text(label, class_name="score-label"), rx.text(ABILITY_LABELS[name], class_name="score-full-label"), justify="between", width="100%"),
        rx.input(
            name=name,
            default_value=AppState.builder_scores[name],
            on_blur=lambda value: AppState.set_builder_score(name, value),
            key=AppState.builder_form_key + "-" + AppState.builder_class + "-" + name,
            class_name="score-input",
        ),
        rx.cond(
            AppState.is_builder_editing,
            rx.fragment(),
            rx.hstack(
                rx.text("Race", class_name="score-meta-label"),
                rx.text(AppState.builder_bonus_labels[name], class_name="bonus-pill"),
                rx.spacer(),
                rx.text("Final", class_name="score-meta-label"),
                rx.text(AppState.builder_final_scores[name], class_name="score-total"),
                width="100%",
                align="center",
            ),
        ),
        class_name="score-box",
    )


def score_summary_row(row: rx.Var[dict]) -> rx.Component:
    return rx.hstack(
        rx.text(row["label"], class_name="score-summary-label"),
        rx.spacer(),
        rx.text(row["base"], class_name="score-summary-value"),
        rx.text(row["bonus"], class_name="bonus-pill small"),
        rx.text("=", class_name="score-summary-equals"),
        rx.text(row["total"], class_name="score-summary-total"),
        class_name="score-summary-row",
    )


def delete_character_dialog() -> rx.Component:
    """Delete button with an explicit confirmation before anything is removed."""
    return rx.alert_dialog.root(
        rx.alert_dialog.trigger(
            rx.button(rx.icon("trash-2", size=16), rx.text("Delete"), class_name="icon-button danger"),
        ),
        rx.alert_dialog.content(
            rx.alert_dialog.title("Delete ", AppState.primary_character["name"], "?"),
            rx.alert_dialog.description(
                "This permanently deletes the character and detaches them from every campaign they play in. "
                "Campaign memberships stay — only the character is removed. This cannot be undone.",
            ),
            rx.flex(
                rx.alert_dialog.cancel(rx.button("Keep character", class_name="secondary-action")),
                rx.alert_dialog.action(
                    rx.button(
                        "Delete forever",
                        on_click=lambda: AppState.delete_character(AppState.primary_character["id"]),
                        class_name="icon-button danger",
                    ),
                ),
                spacing="3",
                justify="end",
                margin_top="16px",
            ),
        ),
    )


def character_switcher() -> rx.Component:
    """Chips for every character the user owns; click to swap the sheet."""
    return rx.box(
        rx.text("MY CHARACTERS", class_name="eyebrow"),
        rx.hstack(
            rx.foreach(
                AppState.characters,
                lambda character: rx.button(
                    character["name"],
                    on_click=lambda: AppState.view_character(character["id"]),
                    class_name=rx.cond(
                        character["id"] == AppState.effective_character_id,
                        "tab active",
                        "tab",
                    ),
                ),
            ),
            rx.button(
                rx.icon("plus", size=16),
                rx.text("New"),
                on_click=AppState.start_new_character,
                class_name="tab",
            ),
            class_name="segmented scroll-tabs",
        ),
    )


def character_sheet() -> rx.Component:
    return shell(
        rx.cond(
            AppState.has_characters,
            rx.vstack(
            character_switcher(),
            rx.box(
                rx.grid(
                    rx.box(
                        rx.text(AppState.primary_character["ancestry"], " ", AppState.primary_character["background"], class_name="eyebrow"),
                        rx.heading(AppState.primary_character["name"], class_name="sheet-title"),
                        rx.text(AppState.primary_character["character_class"], " level ", AppState.primary_character["level"], class_name="lead"),
                        rx.hstack(
                            rx.button(
                                rx.icon("pencil", size=16),
                                rx.text("Edit"),
                                on_click=lambda: AppState.start_edit_character(AppState.primary_character["id"]),
                                class_name="secondary-action",
                            ),
                            delete_character_dialog(),
                            spacing="2",
                            class_name="sheet-actions",
                        ),
                        class_name="sheet-identity",
                    ),
                    rx.grid(
                        stat_tile("AC", AppState.primary_stats["ac"]),
                        stat_tile("HP", AppState.primary_stats["hp"], "max"),
                        stat_tile("INIT", AppState.primary_stats["initiative"]),
                        stat_tile("PROF", AppState.primary_stats["proficiency"]),
                        columns="4",
                        spacing="3",
                        class_name="sheet-stat-grid",
                    ),
                    columns="2",
                    spacing="4",
                    class_name="sheet-hero",
                ),
                class_name="sheet-top",
            ),
            sheet_tabs(),
            rx.cond(AppState.sheet_tab == "skills", skills_saves_panel(), rx.fragment()),
            rx.cond(AppState.sheet_tab == "features", features_panel(), rx.fragment()),
            rx.cond(AppState.sheet_tab == "inventory", inventory_panel(), rx.fragment()),
            rx.cond(AppState.sheet_tab == "spells", spells_panel(), rx.fragment()),
            rx.cond(AppState.sheet_tab == "notes", notes_panel(), rx.fragment()),
            spacing="4",
            ),
            empty_state("No character sheet yet", "Create a character from the builder and this page will become their playable sheet."),
        )
    )


def sheet_tabs() -> rx.Component:
    return rx.hstack(
        rx.button("Skills & Saves", on_click=AppState.set_sheet_tab("skills"), class_name=rx.cond(AppState.sheet_tab == "skills", "tab active", "tab")),
        rx.button("Features", on_click=AppState.set_sheet_tab("features"), class_name=rx.cond(AppState.sheet_tab == "features", "tab active", "tab")),
        rx.button("Inventory", on_click=AppState.set_sheet_tab("inventory"), class_name=rx.cond(AppState.sheet_tab == "inventory", "tab active", "tab")),
        rx.button("Spells", on_click=AppState.set_sheet_tab("spells"), class_name=rx.cond(AppState.sheet_tab == "spells", "tab active", "tab")),
        rx.button("Notes", on_click=AppState.set_sheet_tab("notes"), class_name=rx.cond(AppState.sheet_tab == "notes", "tab active", "tab")),
        class_name="segmented scroll-tabs",
    )


def skills_saves_panel() -> rx.Component:
    return rx.grid(
        rx.box(
            rx.heading("Skills", class_name="section-heading"),
            rx.grid(
                stat_tile("Perception", AppState.primary_stats["perception"], "WIS + prof"),
                stat_tile("Stealth", AppState.primary_stats["stealth"], "DEX"),
                stat_tile("Insight", "+7", "WIS + prof"),
                stat_tile("Athletics", "+4", "STR + prof"),
                columns="2",
                spacing="3",
            ),
            class_name="panel",
        ),
        rx.box(
            rx.heading("Saving Throws", class_name="section-heading"),
            rx.grid(
                stat_tile("STR", "+4"),
                stat_tile("DEX", "+2"),
                stat_tile("CON", "+5"),
                stat_tile("WIS", "+7"),
                columns="2",
                spacing="3",
            ),
            class_name="panel",
        ),
        columns="2",
        spacing="4",
        class_name="two-col",
    )


def features_panel() -> rx.Component:
    return rx.box(
        rx.heading("Features & Traits", class_name="section-heading"),
        rx.grid(
            feature_card("Class Features", "Channel Divinity, prepared spells, ritual casting, and domain features live here."),
            feature_card("Ancestry Traits", "SRD ancestry movement, languages, senses, and proficiencies are displayed without non-SRD content."),
            feature_card("Background", "Feature text and starting proficiencies sourced from the local rules database after seeding."),
            columns="3",
            spacing="3",
        ),
        class_name="panel",
    )


def inventory_panel() -> rx.Component:
    return rx.box(
        rx.heading("Inventory", class_name="section-heading"),
        rx.grid(
            feature_card("Armor", "Scale mail, shield, holy symbol"),
            feature_card("Weapons", "Mace, light crossbow, 20 bolts"),
            feature_card("Adventuring Gear", "Explorer's pack, healer's kit, 37 gp"),
            columns="3",
            spacing="3",
        ),
        class_name="panel",
    )


def spells_panel() -> rx.Component:
    return rx.box(
        rx.heading("Spells", class_name="section-heading"),
        rx.grid(
            stat_tile("Save DC", AppState.primary_stats["spell_dc"]),
            stat_tile("Attack", AppState.primary_stats["spell_attack"]),
            stat_tile("Prepared", "9"),
            columns="3",
            spacing="3",
        ),
        rx.grid(
            feature_card("Cantrips", "Guidance, Sacred Flame, Thaumaturgy"),
            feature_card("1st Level", "Bless, Cure Wounds, Guiding Bolt"),
            feature_card("2nd Level", "Lesser Restoration, Spiritual Weapon"),
            feature_card("3rd Level", "Revivify, Spirit Guardians"),
            columns="4",
            spacing="3",
            class_name="spell-grid",
        ),
        class_name="panel",
    )


def notes_panel() -> rx.Component:
    return rx.box(
        rx.heading("Notes", class_name="section-heading"),
        rx.text(AppState.primary_character["notes"], class_name="body-text"),
        rx.text_area(default_value="Session notes, loot reminders, allies, grudges, and plans.", class_name="textarea tall"),
        class_name="panel",
    )


def feature_card(title: str, body: str) -> rx.Component:
    return rx.box(rx.heading(title, class_name="mini-heading"), rx.text(body, class_name="body-text"), class_name="mini-card")


def campaign_page() -> rx.Component:
    return shell(
        rx.cond(
            AppState.has_active_campaign,
            rx.vstack(
                rx.box(
                    rx.text("CAMPAIGN", class_name="eyebrow"),
                    rx.heading(AppState.campaign["name"], class_name="page-title"),
                    rx.hstack(
                        rx.text("Your role: ", rx.text(AppState.campaign["role"], as_="span", class_name="code-text"), class_name="lead"),
                        rx.button(
                            rx.icon("copy", size=16),
                            rx.text(AppState.invite_code),
                            on_click=rx.set_clipboard(AppState.invite_code),
                            title="Copy invite code",
                            class_name="secondary-action",
                        ),
                        spacing="3",
                        align="center",
                    ),
                    rx.cond(
                        AppState.is_campaign_dm,
                        rx.text("Share this invite code with your players — they enter it under Join a Campaign.", class_name="hint"),
                        rx.fragment(),
                    ),
                    class_name="page-intro",
                ),
                rx.hstack(
                    rx.button("Hub", on_click=AppState.set_campaign_tab("hub"), class_name=rx.cond(AppState.campaign_tab == "hub", "tab active", "tab")),
                    rx.cond(
                        AppState.is_campaign_dm,
                        rx.button("DM View", on_click=AppState.set_campaign_tab("dm"), class_name=rx.cond(AppState.campaign_tab == "dm", "tab active", "tab")),
                        rx.fragment(),
                    ),
                    class_name="segmented",
                ),
                rx.cond(AppState.campaign_tab == "hub", campaign_hub(), dm_view()),
                spacing="4",
            ),
            rx.vstack(empty_state("No campaign selected", "Host a campaign or join one from your dashboard."), host_campaign_panel(), join_campaign_panel(), spacing="4"),
        )
    )


def session_log_panel() -> rx.Component:
    """Session log: editable for the DM, read-only for players."""
    return rx.box(
        rx.heading("Session Log", class_name="section-heading"),
        rx.cond(
            AppState.is_campaign_dm,
            rx.vstack(
                rx.text_area(
                    default_value=AppState.campaign["session_log"],
                    on_blur=AppState.save_session_log,
                    placeholder="What happened last session?",
                    key=AppState.campaign["id"].to_string() + "-log",
                    class_name="textarea tall",
                ),
                rx.input(
                    default_value=AppState.campaign["next_session"],
                    on_blur=AppState.save_next_session,
                    placeholder="Next session date/time",
                    key=AppState.campaign["id"].to_string() + "-next",
                    class_name="field",
                ),
                rx.text("Saves automatically when you click away.", class_name="hint"),
                spacing="2",
                align="stretch",
            ),
            rx.vstack(
                rx.text(AppState.campaign["session_log"], class_name="body-text"),
                rx.hstack(rx.icon("calendar-days", size=18), rx.text(AppState.campaign["next_session"], class_name="meta-text"), spacing="2"),
                spacing="2",
                align="start",
            ),
        ),
        class_name="panel",
    )


def my_character_panel() -> rx.Component:
    """Attach or swap which of your characters is playing in this campaign."""
    return rx.box(
        rx.heading("My Character", class_name="section-heading"),
        rx.cond(
            AppState.has_campaign_character,
            rx.text(
                "Playing as ",
                rx.text(AppState.campaign["my_character_name"], as_="span", class_name="accent-text"),
                class_name="body-text",
            ),
            rx.text("You have not attached a character to this campaign yet.", class_name="body-text"),
        ),
        rx.cond(
            AppState.has_characters,
            rx.vstack(
                rx.select(
                    AppState.character_choices,
                    placeholder="Pick a character",
                    on_change=AppState.set_assign_character_choice,
                    class_name="field",
                ),
                rx.button(
                    rx.cond(AppState.has_campaign_character, "Switch character", "Attach character"),
                    on_click=AppState.attach_character_to_campaign,
                    class_name="primary-action",
                ),
                rx.text("The same character can play in as many campaigns as you like.", class_name="hint"),
                rx.text(AppState.app_message, class_name="form-note"),
                spacing="3",
                align="stretch",
            ),
            rx.vstack(
                rx.text("You need a character first.", class_name="hint"),
                rx.button("Open the Character Builder", on_click=lambda: AppState.go("builder"), class_name="secondary-action"),
                spacing="2",
                align="start",
            ),
        ),
        class_name="panel",
    )


def campaign_hub() -> rx.Component:
    return rx.grid(
        session_log_panel(),
        rx.box(
            rx.heading("Shared Notes", class_name="section-heading"),
            rx.text_area(
                default_value=AppState.campaign["shared_notes"],
                on_blur=AppState.save_shared_notes,
                placeholder="Party plans, clues, loot splits — everyone in the campaign can edit this.",
                key=AppState.campaign["id"].to_string() + "-shared",
                class_name="textarea tall",
            ),
            rx.text("Saves automatically when you click away.", class_name="hint"),
            class_name="panel",
        ),
        rx.box(
            rx.heading("Player Roster", class_name="section-heading"),
            rx.cond(
                AppState.party_summary == "0 characters, 0 need attention",
                empty_state("No characters in this campaign yet", "Players will appear here after they join and attach a character."),
                rx.foreach(AppState.party_members, party_status_row),
            ),
            class_name="panel span-2",
        ),
        rx.box(
            rx.heading("Dice Roller", class_name="section-heading"),
            rx.form(
                rx.hstack(
                    rx.input(name="count", default_value="1", class_name="dice-field"),
                    rx.select(["d4", "d6", "d8", "d10", "d12", "d20", "d100"], name="die", default_value="d20", class_name="dice-field"),
                    rx.input(name="modifier", default_value="0", class_name="dice-field"),
                    rx.button(rx.icon("dice-5", size=18), type="submit", class_name="icon-button strong"),
                    class_name="dice-row",
                ),
                on_submit=AppState.roll_dice,
                reset_on_submit=False,
            ),
            rx.text(AppState.dice_result, class_name="dice-result"),
            class_name="panel",
        ),
        my_character_panel(),
        columns="2",
        spacing="4",
        class_name="campaign-grid",
    )


def dm_view() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.button("Party Status", on_click=AppState.set_dm_tab("status"), class_name=rx.cond(AppState.dm_tab == "status", "tab active", "tab")),
            rx.button("DM Notes", on_click=AppState.set_dm_tab("notes"), class_name=rx.cond(AppState.dm_tab == "notes", "tab active", "tab")),
            rx.button("NPCs", on_click=AppState.set_dm_tab("npcs"), class_name=rx.cond(AppState.dm_tab == "npcs", "tab active", "tab")),
            rx.button("Initiative", on_click=AppState.set_dm_tab("initiative"), class_name=rx.cond(AppState.dm_tab == "initiative", "tab active", "tab")),
            class_name="segmented scroll-tabs",
        ),
        rx.cond(AppState.dm_tab == "status", party_status_board(), rx.fragment()),
        rx.cond(AppState.dm_tab == "notes", dm_notes_panel(), rx.fragment()),
        rx.cond(AppState.dm_tab == "npcs", npc_tracker(), rx.fragment()),
        rx.cond(AppState.dm_tab == "initiative", initiative_tracker(), rx.fragment()),
        spacing="4",
    )


def party_status_board() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text("WHERE WE LEFT OFF", class_name="eyebrow"),
                rx.heading("Party Status Board", class_name="section-heading"),
                rx.text("This is intentionally the first DM view: HP, location, and conditions at a glance.", class_name="body-text"),
                align="start",
            ),
            rx.spacer(),
            rx.button(
                rx.icon("copy", size=18),
                rx.text(AppState.invite_code),
                on_click=rx.set_clipboard(AppState.invite_code),
                title="Copy invite code",
                class_name="secondary-action",
            ),
            width="100%",
        ),
        rx.cond(
            AppState.party_summary == "0 characters, 0 need attention",
            empty_state("No party characters yet", "As players join with characters, HP, location, and conditions will appear here."),
            rx.foreach(AppState.party_members, party_status_row),
        ),
        class_name="panel",
    )


def party_status_row(member: rx.Var[dict]) -> rx.Component:
    return rx.box(
        rx.grid(
            rx.vstack(
                rx.text(member["character"], class_name="row-title"),
                rx.text(member["class_level"], class_name="row-subtitle"),
                spacing="0",
                align="start",
            ),
            rx.vstack(
                rx.hstack(rx.text(member["current_hp"], "/", member["max_hp"], class_name="hp-value"), rx.spacer(), rx.text(member["conditions"], class_name="condition-chip"), width="100%"),
                rx.box(rx.box(class_name="hp-fill", style={"width": member["hp_percent"]}), class_name="hp-track"),
                spacing="2",
            ),
            rx.text(member["location"], class_name="location-text"),
            rx.hstack(
                icon_button("minus", "Damage", lambda: AppState.damage_member(member["id"], 5), "icon-button danger"),
                icon_button("plus", "Heal", lambda: AppState.heal_member(member["id"], 5), "icon-button success"),
                spacing="2",
                justify="end",
            ),
            columns="4",
            spacing="3",
            align="center",
            class_name="status-row-grid",
        ),
        class_name="status-row",
    )


def dm_notes_panel() -> rx.Component:
    return rx.box(
        rx.heading("DM Notes", class_name="section-heading"),
        rx.text_area(
            default_value=AppState.dm_notes,
            on_blur=AppState.save_dm_notes,
            placeholder="Secret plans, plot hooks, and reminders only you can see.",
            key=AppState.campaign["id"].to_string() + "-dm-notes",
            class_name="textarea dm-notes",
        ),
        rx.text("Only the DM sees these. Saves automatically when you click away.", class_name="hint"),
        class_name="panel",
    )


def npc_tracker() -> rx.Component:
    return rx.grid(
        rx.box(
            rx.heading("Quick Add NPC", class_name="section-heading"),
            rx.form(
                rx.vstack(
                    rx.input(name="name", placeholder="NPC or monster name", class_name="field"),
                    rx.input(name="ac", placeholder="AC", default_value="12", class_name="field"),
                    rx.input(name="max_hp", placeholder="Max HP", default_value="10", class_name="field"),
                    rx.input(name="stats", placeholder="Key stats", class_name="field"),
                    rx.button("Add NPC", type="submit", class_name="primary-action"),
                    spacing="3",
                ),
                on_submit=AppState.add_npc,
                reset_on_submit=True,
            ),
            class_name="panel",
        ),
        rx.box(
            rx.heading("NPC / Monster Tracker", class_name="section-heading"),
            rx.foreach(AppState.npcs, npc_row),
            class_name="panel",
        ),
        columns="2",
        spacing="4",
        class_name="two-col",
    )


def npc_row(npc: rx.Var[dict]) -> rx.Component:
    return rx.hstack(
        rx.vstack(rx.text(npc["name"], class_name="row-title"), rx.text(npc["stats"], class_name="row-subtitle"), spacing="0", align="start"),
        rx.spacer(),
        rx.text("AC ", npc["ac"], class_name="metric-pill"),
        rx.text(npc["current_hp"], "/", npc["max_hp"], class_name="hp-pill"),
        class_name="compact-row",
    )


def initiative_tracker() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.heading("Initiative Tracker", class_name="section-heading"),
                rx.text("HP changes here sync back to the party status board for PCs.", class_name="body-text"),
                align="start",
            ),
            rx.spacer(),
            rx.button(rx.icon("skip-forward", size=18), rx.text("Next Turn"), on_click=AppState.next_turn, class_name="primary-action"),
            width="100%",
        ),
        rx.foreach(AppState.initiative, initiative_row),
        class_name="panel",
    )


def initiative_row(row: rx.Var[dict]) -> rx.Component:
    return rx.box(
        rx.grid(
            rx.text(row["initiative"], class_name="initiative-score"),
            rx.vstack(rx.text(row["name"], class_name="row-title"), rx.text(row["type"], class_name="row-subtitle"), spacing="0", align="start"),
            rx.text("AC ", row["ac"], class_name="metric-pill"),
            rx.text(row["current_hp"], "/", row["max_hp"], class_name="hp-pill"),
            rx.hstack(
                icon_button("minus", "Damage", lambda: AppState.damage_combatant(row["key"], 5), "icon-button danger"),
                icon_button("plus", "Heal", lambda: AppState.heal_combatant(row["key"], 5), "icon-button success"),
                spacing="2",
                justify="end",
            ),
            columns="5",
            spacing="3",
            align="center",
            class_name="initiative-row-grid",
        ),
        class_name="status-row",
    )


def route() -> rx.Component:
    return rx.cond(
        AppState.current_view == "auth",
        auth_panel(),
        rx.cond(
            AppState.current_view == "builder",
            character_builder(),
            rx.cond(
                AppState.current_view == "sheet",
                character_sheet(),
                rx.cond(AppState.current_view == "campaign", campaign_page(), dashboard()),
            ),
        ),
    )


def protected_page(content: rx.Component) -> rx.Component:
    return rx.cond(AppState.is_authenticated, content, auth_panel())


app = rx.App(stylesheets=["/styles.css"])
app.add_page(route, route="/", title="DND and Beyond", on_load=AppState.restore_session)
app.add_page(lambda: protected_page(character_builder()), route="/builder", title="DND and Beyond - Builder", on_load=AppState.restore_session)
app.add_page(lambda: protected_page(character_sheet()), route="/sheet", title="DND and Beyond - Character Sheet", on_load=AppState.restore_session)
app.add_page(lambda: protected_page(campaign_page()), route="/campaign", title="DND and Beyond - Campaign", on_load=AppState.restore_session)
