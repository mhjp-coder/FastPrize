import pytest
from fastlite import database

from fastprize.store import PrizeDrawStore


@pytest.fixture
def store(tmp_path):
    return PrizeDrawStore(tmp_path / "draws.sqlite3")


def test_csv_import_deduplicates_entrants_and_keeps_prize_copies(store):
    event_id = store.create_event("Launch day")

    entrants = store.import_entrants(
        event_id,
        "name,organization\nAda Lovelace,Engine Co\n ada lovelace , ENGINE CO \nGrace Hopper,\n",
    )
    prizes = store.import_prizes(
        event_id,
        "prize_name,sponsor,number\nTravel voucher,Northwind,007\n"
        "Travel voucher,Northwind,008\n",
    )

    assert (entrants.added, entrants.duplicates, entrants.errors) == (2, 1, ())
    assert prizes.added == 2
    assert len(store.prizes(event_id)) == 2
    assert [prize["number"] for prize in store.prizes(event_id)] == ["007", "008"]


def test_admin_accounts_normalize_email_and_password_reset_revokes_session(store):
    admin = store.create_admin("  Operator@Example.COM ", "hash-v1")
    assert admin["email_normalized"] == "operator@example.com"
    assert store.get_admin_by_email("OPERATOR@example.com")["id"] == admin["id"]
    with pytest.raises(ValueError, match="already exists"):
        store.create_admin("operator@example.com", "hash-duplicate")

    assert store.update_admin_password(admin["id"], "hash-v2")
    updated = store.get_admin(admin["id"])
    assert updated["password_hash"] == "hash-v2"
    assert updated["auth_version"] == admin["auth_version"] + 1


def test_admin_disable_guards_last_account_and_persists_login_throttle(store):
    first = store.create_admin("first@example.test", "hash-first")
    second = store.create_admin("second@example.test", "hash-second")
    assert store.set_admin_enabled(first["id"], False)
    assert not store.set_admin_enabled(second["id"], False)
    assert store.get_admin(second["id"])["enabled"] == 1

    assert not store.admin_login_is_limited("operator@example.test", 1000)
    for failure in range(5):
        store.record_admin_login_failure("operator@example.test", 1000 + failure)
    assert store.admin_login_is_limited("operator@example.test", 1005)
    store.clear_admin_login_failures("operator@example.test")
    assert not store.admin_login_is_limited("operator@example.test", 1005)


def test_admin_delete_guards_final_enabled_account_and_reused_ids(store):
    first = store.create_admin("first@example.test", "hash-first")
    second = store.create_admin("second@example.test", "hash-second")
    assert store.delete_admin(second["id"])
    assert store.get_admin(second["id"]) is None
    replacement = store.create_admin("replacement@example.test", "hash-replacement")
    assert replacement["id"] == second["id"]
    assert replacement["auth_version"] != second["auth_version"]
    assert store.set_admin_enabled(replacement["id"], False)
    assert not store.delete_admin(first["id"])
    assert store.delete_admin(replacement["id"])
    assert not store.delete_admin(replacement["id"])
    assert store.get_admin(first["id"])["enabled"] == 1


def test_prize_csv_import_accepts_prize_number_header(store):
    event_id = store.create_event("Awards")

    report = store.import_prizes(
        event_id,
        "prize_name,sponsor,prize_number\nLaptop,Northwind,0042\n",
    )

    assert report.added == 1
    assert store.prizes(event_id)[0]["number"] == "0042"


def test_csv_import_reports_required_name_errors(store):
    event_id = store.create_event("Awards")

    missing_column = store.import_entrants(event_id, "organization\nExample Org\n")
    missing_value = store.import_entrants(event_id, "name,organization\n,Example Org\n")
    missing_prize_column = store.import_prizes(event_id, "sponsor\nNorthwind\n")

    assert missing_column.errors == ("CSV must include a name column.",)
    assert missing_value.errors == ("Row 2: name is required.",)
    assert missing_prize_column.errors == ("CSV must include a prize_name column.",)


def test_draw_removes_winner_when_event_setting_is_enabled(store):
    event_id = store.create_event("Awards")
    entrant_id = store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    prize_id = store.add_prize(event_id, "Laptop", "Northwind")

    result = store.draw(event_id, prize_id, chooser=lambda entrants: entrants[0])

    assert result["entrant_name"] == "Ada Lovelace"
    assert result["prize_name"] == "Laptop"
    assert store.entrants(event_id)[0]["eligible"] == 0
    with pytest.raises(ValueError, match="no eligible entrants"):
        store.draw(event_id, store.add_prize(event_id, "Headphones"))
    assert entrant_id


def test_draw_retains_winner_when_event_setting_is_disabled(store):
    event_id = store.create_event("Awards", remove_winners=False)
    store.add_entrant(event_id, "Ada Lovelace")
    first_prize = store.add_prize(event_id, "Laptop")
    second_prize = store.add_prize(event_id, "Headphones")

    store.draw(event_id, first_prize, chooser=lambda entrants: entrants[0])
    store.draw(event_id, second_prize, chooser=lambda entrants: entrants[0])

    assert store.entrants(event_id)[0]["eligible"] == 1
    assert len(store.draw_history(event_id)) == 2


def test_draw_cannot_award_a_prize_twice_or_cross_events(store):
    first_event = store.create_event("First")
    second_event = store.create_event("Second")
    store.add_entrant(first_event, "Ada Lovelace")
    prize_id = store.add_prize(first_event, "Laptop")

    store.draw(first_event, prize_id, chooser=lambda entrants: entrants[0])

    with pytest.raises(ValueError, match="not available"):
        store.draw(first_event, prize_id)
    with pytest.raises(ValueError, match="not available"):
        store.draw(second_event, prize_id)


def test_return_prize_to_pool_removes_its_draw_history(store):
    event_id = store.create_event("Awards")
    entrant_id = store.add_entrant(event_id, "Ada Lovelace")
    prize_id = store.add_prize(event_id, "Laptop")
    store.draw(event_id, prize_id, chooser=lambda entrants: entrants[0])
    assert store.entrants(event_id)[0]["eligible"] == 0

    assert store.return_prize_to_pool(event_id, prize_id)

    assert store.prizes(event_id)[0]["drawn"] == 0
    assert store.entrants(event_id)[0]["id"] == entrant_id
    assert store.entrants(event_id)[0]["eligible"] == 1
    assert store.draw_history(event_id) == []
    assert not store.return_prize_to_pool(event_id, prize_id)


def test_draw_snapshots_survive_entrant_removal(store):
    event_id = store.create_event("Awards")
    preview_entrant = store.add_entrant(event_id, "Ada Lovelace")
    preview_prize = store.add_prize(event_id, "Laptop")
    preview = store.preview_draw(
        event_id,
        preview_prize,
        chooser=lambda entrants: entrants[0],
    )
    store.save_preview(event_id, preview_prize, preview["winner"], preview["prize"])

    assert store.remove_entrant(event_id, preview_entrant)
    latest_preview = store.latest_preview(event_id)
    assert latest_preview["entrant_id"] is None
    assert latest_preview["entrant_name"] == "Ada Lovelace"

    draw_entrant = store.add_entrant(event_id, "Grace Hopper")
    draw_prize = store.add_prize(event_id, "Headphones")
    store.draw(event_id, draw_prize, chooser=lambda entrants: entrants[0])

    assert store.remove_entrant(event_id, draw_entrant)
    latest_draw = store.latest_draw(event_id)
    assert latest_draw["entrant_id"] is None
    assert latest_draw["entrant_name"] == "Grace Hopper"


def test_clear_all_event_data_removes_entrants_and_prizes(store):
    event_id = store.create_event("Data reset")
    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    store.add_entrant(event_id, "Grace Hopper", "Naval Lab")
    store.add_prize(event_id, "Laptop", "Northwind")
    store.add_prize(event_id, "Travel", "Contoso")

    entrants_removed, prizes_removed = store.clear_all_event_data(event_id)

    assert entrants_removed == 2
    assert prizes_removed == 2
    assert store.entrants(event_id) == []
    assert store.prizes(event_id) == []


def test_delete_event_removes_event_and_cascades_data(store):
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace")
    store.add_prize(event_id, "Laptop")

    assert store.delete_event(event_id)

    assert store.get_event(event_id) is None
    assert store.entrants(event_id) == []
    assert store.prizes(event_id) == []
    assert not store.delete_event(event_id)


def test_legacy_prize_name_column_is_migrated(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    legacy_db = database(str(db_path))
    legacy_db.q(
        """CREATE TABLE prizes (
            id INTEGER PRIMARY KEY,
            event_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sponsor TEXT NOT NULL DEFAULT '',
            drawn INTEGER NOT NULL DEFAULT 0
        )"""
    )
    legacy_db.t.prizes.insert({"event_id": 1, "name": "Laptop", "sponsor": "Northwind"})

    store = PrizeDrawStore(db_path)

    assert "prize_name" in store.db.t.prizes.columns_dict
    assert "name" not in store.db.t.prizes.columns_dict
    assert store.db.t.prizes(as_cls=False)[0]["prize_name"] == "Laptop"
    assert "number" in store.db.t.prizes.columns_dict
    assert store.db.t.prizes(as_cls=False)[0]["number"] == ""
