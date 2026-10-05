from starlette.testclient import TestClient

from fastprize.app import create_app


def test_selected_event_cookie_persists_and_updates(tmp_path):
    app, store = create_app(tmp_path / "selection.sqlite3")
    client = TestClient(app)
    first_id = store.create_event("First event")
    second_id = store.create_event("Second event")

    assert f'href="/events/{first_id}/import"' not in client.get("/").text

    first_selection = client.get(f"/events/{first_id}")
    assert first_selection.cookies.get("fastprize_event_id") == str(first_id)
    first_home = client.get("/")
    assert "<p>First event</p>" in first_home.text
    assert f'href="/events/{first_id}/import"' in first_home.text
    assert f'href="/events/{second_id}/import"' not in first_home.text

    second_selection = client.get(f"/events/{second_id}")
    assert second_selection.cookies.get("fastprize_event_id") == str(second_id)
    second_home = client.get("/")
    assert "<p>Second event</p>" in second_home.text
    assert f'href="/events/{second_id}/import"' in second_home.text
    assert f'href="/events/{first_id}/import"' not in second_home.text

    old_projector_poll = client.get(f"/events/{first_id}/display/latest")
    assert old_projector_poll.status_code == 200
    assert "set-cookie" not in old_projector_poll.headers
    assert client.cookies.get("fastprize_event_id") == str(second_id)

    events_page = client.get("/events")
    assert client.cookies.get("fastprize_event_id") == str(second_id)
    assert f"<p>Second event</p>" in events_page.text


def test_event_workflow_and_live_display(tmp_path):
    app, store = create_app(tmp_path / "web.sqlite3")
    client = TestClient(app)

    home = client.get("/")
    assert home.status_code == 200
    assert "FastPrize" in home.text
    assert "No folded slips." in home.text
    assert 'href="/events"' in home.text
    assert "Create event" not in home.text
    assert "beercss@5.0.3/dist/cdn/beer.min.css" in home.text
    assert "beercss@5.0.3/dist/cdn/beer.min.js" in home.text

    events_page = client.get("/events")
    assert events_page.status_code == 200
    assert "Create event" in events_page.text
    assert 'href="/events/1/import"' not in events_page.text

    workspace = client.post("/events", data={"name": "Launch day"})
    assert workspace.status_code == 200
    assert "Launch day" in workspace.text
    event_id = store.list_events()[0]["id"]
    page_paths = {
        "events": f"/events/{event_id}",
        "import": f"/events/{event_id}/import",
        "entrants": f"/events/{event_id}/entrants",
        "prizes": f"/events/{event_id}/prizes",
        "draw": f"/events/{event_id}/draw",
        "history": f"/events/{event_id}/history",
    }
    selected_home = client.get("/").text
    for section, path in page_paths.items():
        navigation_path = "/events" if section == "events" else path
        assert f'href="{navigation_path}"' in workspace.text
        page = client.get(path)
        assert page.status_code == 200
        assert "<p>Launch day</p>" in page.text
        if section == "events":
            assert f'href="{path}"' not in selected_home
        else:
            assert f'href="{path}"' in selected_home
    assert 'href="/"' in workspace.text
    import_page = client.get(page_paths["import"])
    assert "Import entrants" in import_page.text
    assert "Import prizes" in import_page.text

    imported = client.post(
        f"/events/{event_id}/entrants/import",
        files={"file": ("entrants.csv", "name,organization\nAda Lovelace,Engine Co\n")},
    )
    assert imported.status_code == 200
    assert "Ada Lovelace" in client.get(page_paths["entrants"]).text
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

    preview_page = client.post(f"/events/{event_id}/draws/{prize_id}/preview")
    assert preview_page.status_code == 200
    preview = client.get(
        f"/events/{event_id}/draw?preview={prize_id}&winner={store.entrants(event_id)[0]['id']}"
    )
    assert "Confirm draw" in preview.text
    assert "Award winner" in preview.text
    assert "Redraw" in preview.text

    live_preview = client.get(f"/events/{event_id}/display/latest")
    assert live_preview.status_code == 200
    assert (
        live_preview.json()["entrant_name"]
        == store.latest_preview(event_id)["entrant_name"]
    )

    previous_preview = store.latest_preview(event_id)
    redraw_page = client.post(f"/events/{event_id}/draws/{prize_id}/preview")
    assert redraw_page.status_code == 200
    redrawn_preview = store.latest_preview(event_id)
    assert redrawn_preview["id"] == previous_preview["id"]
    assert redrawn_preview["created_at"] != previous_preview["created_at"]
    live_redraw = client.get(f"/events/{event_id}/display/latest")
    assert live_redraw.json()["created_at"] == redrawn_preview["created_at"]

    winner_id = store.preview_draw(event_id, prize_id)["winner"]["id"]
    award_page = client.post(
        f"/events/{event_id}/draws/{prize_id}/award",
        data={"winner": winner_id},
    )
    assert award_page.status_code == 200
    live_result = client.get(f"/events/{event_id}/display/latest")
    assert live_result.status_code == 200
    assert (
        live_result.json()["entrant_name"]
        == store.latest_draw(event_id)["entrant_name"]
    )
    assert all(entrant["eligible"] for entrant in store.entrants(event_id))
    assert "Laptop" in live_result.text
    assert "Northwind" in live_result.text
    history_page = client.get(page_paths["history"])
    assert store.latest_draw(event_id)["entrant_name"] in history_page.text
    assert "Laptop" in history_page.text


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


def test_operator_can_clear_all_entrants_and_prizes(tmp_path):
    app, store = create_app(tmp_path / "clear.sqlite3")
    client = TestClient(app)
    event_id = store.create_event("Awards")

    client.post(
        f"/events/{event_id}/entrants",
        data={"name": "Ada Lovelace", "organization": "Engine Co"},
    )
    client.post(
        f"/events/{event_id}/entrants",
        data={"name": "Grace Hopper", "organization": "Naval Lab"},
    )
    client.post(
        f"/events/{event_id}/prizes",
        data={"name": "Laptop", "sponsor": "Northwind"},
    )
    client.post(
        f"/events/{event_id}/prizes", data={"name": "Travel", "sponsor": "Contoso"}
    )

    reset_page = client.post(f"/events/{event_id}/clear-data")
    assert "Cleared all entrants and prizes." in reset_page.text
    assert store.entrants(event_id) == []
    assert store.prizes(event_id) == []
