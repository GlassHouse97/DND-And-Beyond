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
