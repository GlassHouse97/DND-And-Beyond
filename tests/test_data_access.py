from dnd_and_beyond import data_access


def test_verified_user_sees_only_their_characters_and_campaign_roles(tmp_path, monkeypatch):
    monkeypatch.setattr(data_access, "DB_PATH", tmp_path / "app.db")

    created, reason = data_access.create_user(
        "dm@example.com",
        "hash-1",
        "DM Friend",
        "verify-dm",
    )
    assert created is True
    assert reason == "created"
    assert data_access.verify_user_email("dm@example.com", "verify-dm") is True
    dm = data_access.get_user_by_email("dm@example.com")

    created, _ = data_access.create_user(
        "player@example.com",
        "hash-2",
        "Player Friend",
        "verify-player",
    )
    assert created is True
    assert data_access.verify_user_email("player@example.com", "verify-player") is True
    player = data_access.get_user_by_email("player@example.com")

    character_id = data_access.create_character(
        player["id"],
        {
            "name": "Test Hero",
            "ancestry": "Human",
            "character_class": "Fighter",
            "background": "Soldier",
            "level": 1,
            "str": 15,
            "dex": 14,
            "con": 14,
            "int": 10,
            "wis": 12,
            "cha": 8,
            "armor": "chain mail",
            "shield": True,
            "skills": "Athletics",
            "saves": "Strength, Constitution",
            "notes": "",
        },
    )

    campaign_id = data_access.create_campaign(dm["id"], "Friday Table", "Friday", "FRIDAY-1234")
    joined, reason = data_access.join_campaign(player["id"], "FRIDAY-1234", character_id)

    assert joined is True
    assert reason == "joined"
    assert data_access.list_user_campaigns(dm["id"])[0]["role"] == "dm"
    assert data_access.list_user_campaigns(player["id"])[0]["role"] == "player"
    assert data_access.list_user_characters(dm["id"]) == []
    assert data_access.list_user_characters(player["id"])[0]["campaign_names"] == "Friday Table"
    assert data_access.get_campaign(campaign_id, player["id"])["role"] == "player"

    # Editing is owner-only and persists every field it changes.
    updated_fields = {
        "name": "Renamed Hero",
        "ancestry": "Dwarf",
        "character_class": "Fighter",
        "background": "Soldier",
        "level": 3,
        "str": 16,
        "dex": 14,
        "con": 15,
        "int": 10,
        "wis": 12,
        "cha": 8,
        "armor": "plate",
        "shield": False,
        "skills": "Athletics, Survival",
        "saves": "Strength, Constitution",
        "weapons": "Longsword, Handaxe",
        "spells": "",
        "notes": "Now level 3",
    }
    assert data_access.update_character(character_id, dm["id"], updated_fields) is False
    assert data_access.update_character(character_id, player["id"], updated_fields) is True
    edited = data_access.get_character(character_id, player["id"])
    assert edited["name"] == "Renamed Hero"
    assert edited["level"] == 3
    assert edited["strength"] == 16
    assert edited["has_shield"] == 0
    assert edited["weapons"] == "Longsword, Handaxe"
    assert edited["spells"] == ""

    # Deleting is owner-only and detaches the character from campaign rosters.
    assert data_access.delete_character(character_id, dm["id"]) is False
    assert data_access.delete_character(character_id, player["id"]) is True
    assert data_access.get_character(character_id, player["id"]) is None
    member = next(
        m for m in data_access.list_campaign_members(campaign_id) if m["user_id"] == player["id"]
    )
    assert member["character_id"] is None
    assert member["current_hp"] == data_access.HP_UNSET


def test_campaign_directory_and_join_request_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(data_access, "DB_PATH", tmp_path / "app.db")

    data_access.create_user("dm@example.com", "hash-1", "The DM", "t-dm")
    data_access.verify_user_email("dm@example.com", "t-dm")
    dm = data_access.get_user_by_email("dm@example.com")
    data_access.create_user("newbie@example.com", "hash-2", "Newbie", "t-newbie")
    data_access.verify_user_email("newbie@example.com", "t-newbie")
    newbie = data_access.get_user_by_email("newbie@example.com")

    campaign_id = data_access.create_campaign(dm["id"], "Open Table", "Sunday", "OPEN-9999")

    # The directory shows the campaign to outsiders WITHOUT the invite code.
    listing = data_access.list_public_campaigns(newbie["id"])
    entry = next(c for c in listing if c["id"] == campaign_id)
    assert entry["dm_name"] == "The DM"
    assert entry["member_count"] == 1
    assert entry["my_status"] == "none"
    assert "invite_code" not in entry

    # Members see themselves as members; the DM is a member.
    assert next(c for c in data_access.list_public_campaigns(dm["id"]))["my_status"] == "member"

    # Request lifecycle: request -> pending -> duplicate blocked.
    ok, reason = data_access.create_join_request(campaign_id, newbie["id"])
    assert ok and reason == "requested"
    ok, reason = data_access.create_join_request(campaign_id, newbie["id"])
    assert not ok and reason == "already_requested"
    assert next(c for c in data_access.list_public_campaigns(newbie["id"]))["my_status"] == "pending"

    requests = data_access.list_pending_join_requests(campaign_id)
    assert len(requests) == 1 and requests[0]["display_name"] == "Newbie"
    request_id = requests[0]["id"]

    # Only the DM can resolve.
    ok, reason = data_access.resolve_join_request(request_id, newbie["id"], approve=True)
    assert not ok and reason == "not_dm"

    # Approval creates the membership as a player with no character yet.
    ok, reason = data_access.resolve_join_request(request_id, dm["id"], approve=True)
    assert ok and reason == "approved"
    member = next(
        m for m in data_access.list_campaign_members(campaign_id) if m["user_id"] == newbie["id"]
    )
    assert member["role"] == "player" and member["character_id"] is None
    assert next(c for c in data_access.list_public_campaigns(newbie["id"]))["my_status"] == "member"
    assert data_access.list_pending_join_requests(campaign_id) == []

    # A resolved request cannot be resolved again; members cannot re-request.
    ok, reason = data_access.resolve_join_request(request_id, dm["id"], approve=False)
    assert not ok and reason == "not_found"
    ok, reason = data_access.create_join_request(campaign_id, newbie["id"])
    assert not ok and reason == "already_member"

    # Decline path: a third user gets declined, then may ask again.
    data_access.create_user("later@example.com", "hash-3", "Later Larry", "t-later")
    data_access.verify_user_email("later@example.com", "t-later")
    larry = data_access.get_user_by_email("later@example.com")
    data_access.create_join_request(campaign_id, larry["id"])
    larry_request = data_access.list_pending_join_requests(campaign_id)[0]["id"]
    ok, reason = data_access.resolve_join_request(larry_request, dm["id"], approve=False)
    assert ok and reason == "declined"
    assert not any(m["user_id"] == larry["id"] for m in data_access.list_campaign_members(campaign_id))
    ok, reason = data_access.create_join_request(campaign_id, larry["id"])
    assert ok and reason == "requested"
