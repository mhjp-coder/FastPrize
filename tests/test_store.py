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
        "prize_name,sponsor\nTravel voucher,Northwind\nTravel voucher,Northwind\n",
    )

    assert (entrants.added, entrants.duplicates, entrants.errors) == (2, 1, ())
    assert prizes.added == 2
    assert len(store.prizes(event_id)) == 2
    assert store.prizes(event_id)[0]["prize_number"] is None


def test_prize_number_is_optional_on_import(store):
    event_id = store.create_event("Awards")

    numbered = store.import_prizes(
        event_id,
        "prize_name,sponsor,prize #\nLaptop,Northwind,12\nMug,Contoso,\n",
    )
    numbered_again = store.import_prizes(
        event_id,
        "prize_name,prize_number\nNotebook,4\nPen,four\n",
    )

    prizes = store.prizes(event_id)
    assert numbered.added == 2
    assert numbered.errors == ()
    assert [(prize["prize_name"], prize["prize_number"]) for prize in prizes] == [
        ("Notebook", 4),
        ("Laptop", 12),
        ("Mug", None),
    ]
    assert numbered_again.added == 1
    assert numbered_again.errors == (
        "Row 3: prize number must be a whole number.",
    )


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


def test_undo_award_removes_the_draw_and_restores_eligibility(store):
    event_id = store.create_event("Awards")
    ada = store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    store.add_entrant(event_id, "Grace Hopper")
    laptop = store.add_prize(event_id, "Laptop", "Northwind")
    headphones = store.add_prize(event_id, "Headphones")
    store.draw(
        event_id,
        laptop,
        chooser=lambda entrants: next(
            entrant for entrant in entrants if entrant["id"] == ada
        ),
    )
    store.draw(
        event_id,
        headphones,
        chooser=lambda entrants: next(
            entrant for entrant in entrants if entrant["name"] == "Grace Hopper"
        ),
    )

    assert store.undo_award(event_id, laptop)

    prizes = {prize["id"]: prize for prize in store.prizes(event_id)}
    assert prizes[laptop]["drawn"] == 0
    assert prizes[headphones]["drawn"] == 1
    history = store.draw_history(event_id)
    assert [draw["prize_name"] for draw in history] == ["Headphones"]
    entrants = {entrant["id"]: entrant for entrant in store.entrants(event_id)}
    assert entrants[ada]["eligible"] == 1
    assert not store.undo_award(event_id, laptop)


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


def test_clear_event_data_removes_only_the_selected_records(store):
    event_id = store.create_event("Data reset")
    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    store.add_entrant(event_id, "Grace Hopper", "Naval Lab")
    laptop = store.add_prize(event_id, "Laptop", "Northwind")
    store.add_prize(event_id, "Travel", "Contoso")
    store.draw(event_id, laptop, chooser=lambda entrants: entrants[0])

    store.clear_event_data(event_id, history=True)

    assert store.draw_history(event_id) == []
    assert len(store.entrants(event_id)) == 2
    assert len(store.prizes(event_id)) == 2

    store.clear_event_data(event_id, entrants=True)

    assert store.entrants(event_id) == []
    assert len(store.prizes(event_id)) == 2

    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    store.clear_event_data(event_id, prizes=True)

    assert store.prizes(event_id) == []
    assert store.entrants(event_id)


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
    assert "prize_number" in store.db.t.prizes.columns_dict
    assert "name" not in store.db.t.prizes.columns_dict
    assert store.db.t.prizes(as_cls=False)[0]["prize_name"] == "Laptop"
