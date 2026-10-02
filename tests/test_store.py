import pytest

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
        event_id, "name,sponsor\nTravel voucher,Northwind\nTravel voucher,Northwind\n"
    )

    assert (entrants.added, entrants.duplicates, entrants.errors) == (2, 1, ())
    assert prizes.added == 2
    assert len(store.prizes(event_id)) == 2


def test_csv_import_reports_required_name_errors(store):
    event_id = store.create_event("Awards")

    missing_column = store.import_entrants(event_id, "organization\nExample Org\n")
    missing_value = store.import_entrants(event_id, "name,organization\n,Example Org\n")

    assert missing_column.errors == ("CSV must include a name column.",)
    assert missing_value.errors == ("Row 2: name is required.",)


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
