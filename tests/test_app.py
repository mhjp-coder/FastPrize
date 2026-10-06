from fasthtml.common import Client

from fastprize.app import create_app


def _test_client(app):
    client = Client(app)
    client.cli.follow_redirects = True
    return client


def test_selected_event_cookie_persists_and_updates(tmp_path):
    app, store = create_app(tmp_path / "selection.sqlite3")
    client = _test_client(app)
    first_id = store.create_event("First event")
    second_id = store.create_event("Second event")

    assert f'href="/events/{first_id}/import"' not in client.get("/").text

    first_selection = client.get(f"/events/{first_id}")
    assert first_selection.cookies.get("fastprize_event_id") == str(first_id)
    first_home = client.get("/")
    assert "First event" in first_home.text
    assert "Your events" not in first_home.text
    assert 'class="card padding tertiary-container small-round"' in first_home.text
    assert first_home.text.count('class="s6 m6 l6 card padding fill small-round"') == 2
    assert 'class="button primary m6 responsive extra"' in first_home.text
    assert f'href="/events/{first_id}/import" class="button primary' in first_home.text
    assert 'class="button secondary m6 responsive extra"' in first_home.text
    assert "<i>upload_file</i><span>Import CSV</span>" in first_home.text
    assert "<i>present_to_all</i><span>Open projector display</span>" in first_home.text
    assert f'href="/events/{first_id}/import"' in first_home.text
    assert f'href="/events/{second_id}/import"' not in first_home.text

    second_selection = client.get(f"/events/{second_id}")
    assert second_selection.cookies.get("fastprize_event_id") == str(second_id)
    second_home = client.get("/")
    assert "Second event" in second_home.text
    assert f'href="/events/{second_id}/import"' in second_home.text
    assert f'href="/events/{first_id}/import"' not in second_home.text

    old_projector_poll = client.get(f"/events/{first_id}/display/latest")
    assert old_projector_poll.status_code == 200
    assert "set-cookie" not in old_projector_poll.headers
    assert client.cli.cookies.get("fastprize_event_id") == str(second_id)

    events_page = client.get("/events")
    assert client.cli.cookies.get("fastprize_event_id") == str(second_id)
    assert "Second event" in events_page.text


def test_home_draw_readiness_message(tmp_path):
    app, store = create_app(tmp_path / "readiness.sqlite3")
    client = _test_client(app)
    event_id = store.create_event("Awards")

    client.get(f"/events/{event_id}")
    home = client.get("/").text
    assert "Add eligible entrants and prizes to get started." in home
    assert f'href="/events/{event_id}/import" class="button primary' in home

    store.add_entrant(event_id, "Ada Lovelace")
    home = client.get("/").text
    assert "Add prizes to get started." in home
    assert f'href="/events/{event_id}/import" class="button primary' in home

    store.add_prize(event_id, "Laptop")
    home = client.get("/").text
    assert "You are Ready to Draw!" in home
    assert f'href="/events/{event_id}/draw" class="button primary' in home
    assert "<i>casino</i><span>Draw</span>" in home

    second_event_id = store.create_event("Raffle")
    store.add_prize(second_event_id, "Headphones")
    client.get(f"/events/{second_event_id}")
    home = client.get("/").text
    assert "Add eligible entrants to get started." in home
    assert f'href="/events/{second_event_id}/import" class="button primary' in home


def test_event_workflow_and_live_display(tmp_path):
    app, store = create_app(tmp_path / "web.sqlite3")
    client = _test_client(app)

    home = client.get("/")
    assert home.status_code == 200
    assert "FastPrize" in home.text
    assert "Draw Center" in home.text
    assert 'href="/assets/fastprize-favicon.svg"' in home.text
    assert "/assets/fastprize-logo.svg" in home.text
    assert "window.updateFastPrizeBrandTheme" in home.text
    assert client.get("/assets/fastprize-logo.svg").status_code == 200
    assert client.get("/assets/fastprize-favicon.svg").status_code == 200
    assert "left drawer large-padding max m l surface-container" in home.text
    assert 'class="bottom-margin"' in home.text
    assert 'style="--_margin: 0.25rem"' in home.text
    assert (
        "Hats are for pulling rabbits, not folded slips. We do it pseudo-randomly."
        in home.text
    )
    assert "Your events" not in home.text
    assert "DRAW OPERATIONS" not in home.text
    assert 'href="/events"' in home.text
    assert "Create event" not in home.text
    assert "beercss@5.0.3/dist/cdn/beer.min.css" in home.text
    assert "beercss@5.0.3/dist/cdn/beer.min.js" in home.text
    assert "htmx.org@" in home.text
    assert "fonts.googleapis.com/css2?family=Roboto+Flex" in home.text
    assert "--font:" in home.text
    assert (
        "material-dynamic-colors@1.1.4/dist/cdn/material-dynamic-colors.min.js"
        in home.text
    )
    assert "window.setFastPrizeTheme" in home.text
    assert '<body class="light"' in home.text
    assert "<style" not in home.text.lower()
    assert "class-=" not in home.text
    assert "font-variation-settings: 'FILL' 0" in home.text

    events_page = client.get("/events")
    assert events_page.status_code == 200
    assert events_page.text.count('<hr class="medium-divider">') == 3
    divider = '<hr class="medium-divider">'
    first_divider = events_page.text.index(divider)
    second_divider = events_page.text.index(divider, first_divider + len(divider))
    third_divider = events_page.text.index(divider, second_divider + len(divider))
    assert events_page.text.index("Choose your event.") < first_divider
    assert first_divider < events_page.text.index("Create an event")
    assert events_page.text.index("Create an event") < second_divider
    assert second_divider < events_page.text.index("Your events")
    assert events_page.text.index("Your events") < third_divider
    assert "EVENTS" not in events_page.text
    assert 'class="vertical bottom-padding"' in events_page.text
    assert 'class="grid middle-align bottom-padding"' in events_page.text
    assert (
        "font-variation-settings: 'FILL' 0; color: var(--primary)" in events_page.text
    )
    assert "Create event" in events_page.text
    assert 'class="s12 m7 l9 field label border round fill extra"' in events_page.text
    assert '<label for="event-name">Event name</label>' in events_page.text
    assert 'class="s12 m5 l3 responsive fill extra"' in events_page.text
    assert "<i>add</i><span>Create event</span>" in events_page.text
    assert '<footer class="fill fixed s">' in events_page.text
    assert 'aria-label="Events"' in events_page.text
    assert events_page.text.index('id="event-name"') < events_page.text.index(
        "Your events"
    )
    assert "Open event workspace" not in events_page.text
    assert 'href="/events/1/import"' not in events_page.text

    workspace = client.post("/events", data={"name": "Launch day"})
    assert workspace.status_code == 200
    assert "Launch day" in workspace.text
    assert "EVENT MANAGEMENT" not in workspace.text
    assert "Event tasks" not in workspace.text
    assert "Open projector display" not in workspace.text
    assert 'class="active bottom-margin"' in workspace.text
    assert workspace.text.count('class="s12 m6 l6 card padding fill small-round"') == 2
    assert workspace.text.count("<strong>0</strong>") == 4
    assert workspace.text.count('class="vertical bottom-padding"') == 2
    assert all(
        label in workspace.text
        for label in ("Entrants", "total", "eligible", "Prizes", "available")
    )
    assert 'class="switch"' in workspace.text
    assert 'type="checkbox"' in workspace.text
    assert 'aria-label="Remove winners from future draws"' in workspace.text
    assert 'hx-post="/events/1/settings"' in workspace.text
    assert 'hx-trigger="change"' in workspace.text
    assert 'hx-target="#remove-winners-help"' in workspace.text
    assert 'hx-swap="outerHTML"' in workspace.text
    assert 'id="remove-winners-help"' in workspace.text
    assert "fetch(this.action" not in workspace.text
    assert "Drawn winners are removed from future draws." in workspace.text
    assert "Choose whether winners can be selected again." not in workspace.text
    assert "Save setting" not in workspace.text
    assert 'class="s12 responsive extra error"' in workspace.text
    assert "<i>delete</i><span>Clear all entrants and prizes</span>" in workspace.text
    assert "Manage" in workspace.text
    assert "Overview" not in workspace.text
    event_management_page = client.get("/events").text
    assert "Open event workspace" not in event_management_page
    assert "Launch day" in event_management_page
    assert "responsive center-align" in event_management_page
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
        assert "Launch day" in page.text
        assert f'href="{path}"' in selected_home
    assert 'href="/"' in workspace.text
    import_page = client.get(page_paths["import"])
    assert "Entrants CSV" in import_page.text
    assert "Prizes CSV" in import_page.text
    assert "Import selected files" in import_page.text
    assert import_page.text.count('type="file"') == 2
    assert import_page.text.count('onclick="this.nextElementSibling.click()"') == 2
    assert import_page.text.count("attach_file") == 2
    assert import_page.text.count('type="submit"') == 1

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

    combined_import = client.post(
        f"/events/{event_id}/import",
        files={
            "entrants_file": (
                "entrants.csv",
                "name,organization\nKatherine Johnson,NASA\n",
            ),
            "prizes_file": (
                "prizes.csv",
                "prize_name,sponsor\nCoffee basket,Contoso\n",
            ),
        },
    )
    assert "Imported 1 entrant and 1 prize" in combined_import.text
    assert any(
        entrant["name"] == "Katherine Johnson" for entrant in store.entrants(event_id)
    )
    assert any(
        prize["prize_name"] == "Coffee basket" for prize in store.prizes(event_id)
    )

    prize_only_import = client.post(
        f"/events/{event_id}/import",
        files={
            "prizes_file": (
                "prizes.csv",
                "prize_name,sponsor\nGift card,Fabrikam\n",
            )
        },
    )
    assert "Imported 1 prize" in prize_only_import.text
    assert any(prize["prize_name"] == "Gift card" for prize in store.prizes(event_id))

    settings_page = client.post(
        f"/events/{event_id}/settings", headers={"HX-Request": "true"}
    )
    assert settings_page.status_code == 200
    assert store.get_event(event_id)["remove_winners"] == 0
    assert "Previous winners remain eligible." in settings_page.text
    assert "Winner eligibility setting updated." not in settings_page.text
    assert 'class="snackbar' not in settings_page.text

    settings_page = client.post(
        f"/events/{event_id}/settings",
        data={"remove_winners": "1"},
        headers={"HX-Request": "true"},
    )
    assert settings_page.status_code == 200
    assert store.get_event(event_id)["remove_winners"] == 1
    assert "Drawn winners are removed from future draws." in settings_page.text
    settings_page = client.post(f"/events/{event_id}/settings")
    assert store.get_event(event_id)["remove_winners"] == 0
    assert "Previous winners remain eligible." in settings_page.text

    prize_page = client.post(
        f"/events/{event_id}/prizes",
        data={"name": "Laptop", "sponsor": "Northwind"},
    )
    assert "Laptop" in prize_page.text
    prize_id = next(
        prize["id"]
        for prize in store.prizes(event_id)
        if prize["prize_name"] == "Laptop"
    )

    initial_display = client.get(f"/events/{event_id}/display")
    assert initial_display.status_code == 200
    assert '<body class="dark"' in initial_display.text
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
    client = _test_client(app)
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
    client = _test_client(app)
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
    assert (
        'role="status" aria-live="polite" class="s12 chip tertiary">Data cleared</span>'
        in reset_page.text
    )
    clear_form = reset_page.text.split(f'action="/events/{event_id}/clear-data"', 1)[
        1
    ].split(">", 1)[0]
    assert 'class="s12 grid"' in clear_form
    assert "Cleared all entrants and prizes." not in reset_page.text
    assert store.entrants(event_id) == []
    assert store.prizes(event_id) == []
