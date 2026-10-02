from starlette.testclient import TestClient

from fastprize.app import create_app


def test_event_workflow_and_live_display(tmp_path):
    app, store = create_app(tmp_path / "web.sqlite3")
    client = TestClient(app)

    home = client.get("/")
    assert home.status_code == 200
    assert "Make the moment count." in home.text

    workspace = client.post("/events", data={"name": "Launch day"})
    assert workspace.status_code == 200
    assert "Launch day" in workspace.text
    event_id = store.list_events()[0]["id"]

    imported = client.post(
        f"/events/{event_id}/entrants/import",
        files={"file": ("entrants.csv", "name,organization\nAda Lovelace,Engine Co\n")},
    )
    assert imported.status_code == 200
    assert "Ada Lovelace" in imported.text
    assert (
        "Imported 1 entrant; 0 duplicate rows skipped; 0 invalid rows." in imported.text
    )

    import_report = client.post(
        f"/events/{event_id}/entrants/import",
        files={
            "file": (
                "entrants.csv",
                "name,organization\nGrace Hopper,\nAda Lovelace,Engine Co\n,Missing Name Org\n",
            )
        },
    )
    assert (
        "Imported 1 entrant; 1 duplicate row skipped; 1 invalid row."
        in import_report.text
    )
    assert "Row 4: name is required." in import_report.text

    client.post(f"/events/{event_id}/settings", data={"remove_winners": "0"})
    assert store.get_event(event_id)["remove_winners"] == 0

    prize_page = client.post(
        f"/events/{event_id}/prizes",
        data={"name": "Laptop", "sponsor": "Northwind"},
    )
    assert "Laptop" in prize_page.text
    prize_id = store.prizes(event_id)[0]["id"]

    initial_display = client.get(f"/events/{event_id}/display")
    assert initial_display.status_code == 200
    assert "The next name could be yours." in initial_display.text

    result_page = client.post(f"/events/{event_id}/draws/{prize_id}")
    assert result_page.status_code == 200
    live_result = client.get(f"/events/{event_id}/display/latest")
    assert live_result.status_code == 200
    assert (
        live_result.json()["entrant_name"]
        == store.latest_draw(event_id)["entrant_name"]
    )
    assert all(entrant["eligible"] for entrant in store.entrants(event_id))
    assert "Laptop" in live_result.text
    assert "Northwind" in live_result.text


def test_operator_can_edit_and_remove_entrants_and_prizes(tmp_path):
    app, store = create_app(tmp_path / "manage.sqlite3")
    client = TestClient(app)
    event_id = store.create_event("Awards")

    client.post(
        f"/events/{event_id}/entrants",
        data={"name": "Ada Lovelace", "organization": "Engine Co"},
    )
    entrant_id = store.entrants(event_id)[0]["id"]
    edited_entrant = client.post(
        f"/events/{event_id}/entrants/{entrant_id}/edit",
        data={"name": "Ada Byron", "organization": "Analytical Engines"},
    )
    assert "Ada Byron" in edited_entrant.text
    assert store.entrants(event_id)[0]["organization"] == "Analytical Engines"
    client.post(f"/events/{event_id}/entrants/{entrant_id}/remove")
    assert store.entrants(event_id) == []

    client.post(
        f"/events/{event_id}/prizes",
        data={"name": "Laptop", "sponsor": "Northwind"},
    )
    prize_id = store.prizes(event_id)[0]["id"]
    edited_prize = client.post(
        f"/events/{event_id}/prizes/{prize_id}/edit",
        data={"name": "Tablet", "sponsor": "Contoso"},
    )
    assert "Tablet" in edited_prize.text
    assert store.prizes(event_id)[0]["sponsor"] == "Contoso"
    client.post(f"/events/{event_id}/prizes/{prize_id}/remove")
    assert store.prizes(event_id) == []
