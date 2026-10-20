import re

from fasthtml.common import Client

from fastprize.app import create_app
from fastprize.auth import hash_password
from fastprize.ui import TECHNOLOGY_QUOTES, winner_fragment


def _test_client(app, *, login: bool = True):
    client = Client(app)
    client.cli.follow_redirects = True
    client.cli.headers.update({"Origin": "http://testserver"})
    if not login:
        return client
    store = app.state.store
    if store.get_admin_by_email("test-admin@example.test") is None:
        store.create_admin(
            "test-admin@example.test", hash_password("test-password-123")
        )
    login_page = client.get("/login").text
    assert "login-brand" in login_page
    assert login_page.index("login-brand") < login_page.index("<h1")
    csrf_token = login_page.split('name="csrf" value="', 1)[1].split('"', 1)[0]
    client.post(
        "/login",
        data={
            "email": "test-admin@example.test",
            "password": "test-password-123",
            "csrf": csrf_token,
        },
    )
    return client


def test_selected_event_cookie_persists_and_updates(tmp_path):
    app, store = create_app(tmp_path / "selection.sqlite3")
    client = _test_client(app)
    first_id = store.create_event("First event")
    second_id = store.create_event("Second event")

    unselected_home = client.get("/")
    assert "Your events" in unselected_home.text
    assert f'href="/events/{first_id}"' in unselected_home.text
    assert f'href="/events/{second_id}"' in unselected_home.text
    assert f'href="/events/{first_id}/entrants"' not in unselected_home.text

    first_selection = client.get(f"/events/{first_id}")
    assert first_selection.cookies.get("fastprize_event_id") == str(first_id)
    first_home = client.get("/")
    assert "First event" in first_home.text
    assert "Your events" not in first_home.text
    assert f'href="/events/{first_id}/entrants"' in first_home.text
    assert f'href="/events/{second_id}"' not in first_home.text

    second_selection = client.get(f"/events/{second_id}")
    assert second_selection.cookies.get("fastprize_event_id") == str(second_id)
    second_home = client.get("/")
    assert "Second event" in second_home.text
    assert f'href="/events/{second_id}/entrants"' in second_home.text
    assert f'href="/events/{first_id}/entrants"' not in second_home.text

    old_projector_poll = client.get(f"/events/{first_id}/display/latest")
    assert old_projector_poll.status_code == 200
    assert "set-cookie" not in old_projector_poll.headers
    assert client.cli.cookies.get("fastprize_event_id") == str(second_id)

    events_page = client.get("/events")
    assert client.cli.cookies.get("fastprize_event_id") == str(second_id)
    assert "Second event" in events_page.text


def test_event_workflow_and_live_display(tmp_path):
    app, store = create_app(tmp_path / "web.sqlite3")
    client = _test_client(app)

    home = client.get("/")
    assert home.status_code == 200
    assert "FastPrize" in home.text
    assert 'class="brand-mark"' in home.text
    assert "No folded slips." in home.text
    assert 'href="/events"' in home.text
    assert "Create event" not in home.text
    assert "No events yet." in home.text
    assert "/assets/vendor/franken.css" in home.text
    assert "/assets/vendor/tailwind.js" in home.text
    assert "/assets/app.css" in home.text
    assert "beercss" not in home.text
    assert 'class="bg-background text-foreground"' in home.text
    for theme in (
        "slate",
        "stone",
        "gray",
        "neutral",
        "zinc",
        "red",
        "rose",
        "orange",
        "green",
        "blue",
        "yellow",
        "violet",
    ):
        assert f"uk-theme-{theme}" in home.text
    for radius in ("none", "sm", "md", "lg"):
        assert f"uk-radii-{radius}" in home.text
    for shadow in ("none", "sm", "md", "lg"):
        assert f"uk-shadows-{shadow}" in home.text
    assert 'data-key="radii"' in home.text
    assert 'data-key="shadows"' in home.text
    assert "Glow" in home.text
    assert 'data-key="font"' in home.text
    assert "uk-font-sm" in home.text
    assert "uk-font-base" in home.text
    assert 'value="uk-theme-blue" data-hex="#2563eb" selected' in home.text
    assert 'value="uk-radii-lg" selected' in home.text
    assert 'value="uk-shadows-sm" selected' in home.text
    assert 'value="uk-font-base" selected' in home.text
    assert 'value="dark" data-icon="moon" selected' in home.text
    assert '__FRANKEN__.theme || "uk-theme-blue"' in home.text
    assert '__FRANKEN__.radii || "uk-radii-lg"' in home.text
    assert '__FRANKEN__.shadows || "uk-shadows-sm"' in home.text
    assert '__FRANKEN__.font || "uk-font-base"' in home.text
    assert 'if (__FRANKEN__.mode === "light")' in home.text
    assert "<style" not in home.text.lower()
    assert "class-=" not in home.text

    events_page = client.get("/events")
    assert events_page.status_code == 200
    assert "Create event" in events_page.text
    assert "Open event workspace" not in events_page.text
    assert 'href="/events/1/entrants"' not in events_page.text

    workspace = client.post("/events", data={"name": "Launch day"})
    assert workspace.status_code == 200
    assert "Launch day" in workspace.text
    event_management_page = client.get("/events").text
    assert "Open event workspace" not in event_management_page
    assert "Launch day" in event_management_page
    assert "Draw" in event_management_page
    assert "Live display" in event_management_page
    event_id = store.list_events()[0]["id"]
    page_paths = {
        "events": f"/events/{event_id}",
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
    manage_page = client.get(page_paths["events"])
    assert "Entrants CSV" in manage_page.text
    assert "Prizes CSV" in manage_page.text
    assert "Import names and organizations." not in manage_page.text
    assert "Import prize names, numbers, and sponsors." not in manage_page.text
    assert "Name is required. Organization is optional." in manage_page.text
    assert (
        "data-uk-tooltip=\"title: Name is required. Organization is optional."
        "&lt;br&gt;&lt;br&gt;CSV columns: name, organization\""
        in manage_page.text
    )
    assert "class=\"info-tip\"" not in manage_page.text
    assert (
        "Prize name is required. Sponsor and prize number are optional."
        in manage_page.text
    )
    assert "CSV columns: prize_name, sponsor, number or prize_number" in manage_page.text
    assert "Import selected files" in manage_page.text
    assert "Winners are removed from future draws?" in manage_page.text
    assert ">Yes<" in manage_page.text
    assert "Remove all entrants and prizes from this event." not in manage_page.text
    assert "Data management" in manage_page.text
    assert manage_page.text.index("Import selected files") < manage_page.text.index(
        "Data management"
    )
    assert manage_page.text.count('type="file"') == 2
    assert manage_page.text.count('icon="paperclip"') == 2
    assert 'id="confirm-delete"' in manage_page.text
    assert f'href="/events/{event_id}/import"' not in selected_home
    old_import = client.get(f"/events/{event_id}/import")
    assert old_import.status_code == 200
    assert "Import selected files" in old_import.text

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

    kept_eligible = client.post(
        f"/events/{event_id}/settings", data={"remove_winners": "0"}
    )
    assert store.get_event(event_id)["remove_winners"] == 0
    assert ">No<" in kept_eligible.text
    assert ">Yes<" not in kept_eligible.text
    assert kept_eligible.text.count("Winner eligibility setting updated.") == 1
    assert 'class="toast toast-info"' in kept_eligible.text
    assert 'aria-label="Dismiss"' in kept_eligible.text

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
    assert "The next name could be yours." in initial_display.text

    preview_page = client.post(f"/events/{event_id}/draws/{prize_id}/preview")
    assert preview_page.status_code == 200
    assert "prizes remaining" in preview_page.text
    assert 'class="list-search"' in preview_page.text
    assert preview_page.text.index('id="search-prize-list"') < preview_page.text.index(
        'id="prize-list"'
    )
    preview = client.get(
        f"/events/{event_id}/draw?preview={prize_id}&winner={store.entrants(event_id)[0]['id']}"
    )
    assert "Confirm draw" in preview.text
    assert 'aria-label="Close"' in preview.text
    assert "<h2" in preview.text
    winner = store.entrants(event_id)[0]
    assert f"<strong>{winner['name']}</strong>" in preview.text
    if winner["organization"]:
        assert f"<strong>{winner['organization']}</strong>" in preview.text
    assert "<strong>Laptop</strong>" in preview.text
    assert "<strong>Northwind</strong>" in preview.text
    assert "Award winner" in preview.text
    assert "Redraw" in preview.text
    award_button = next(
        button
        for button in re.findall(r"<button\b[^>]*>.*?</button>", preview.text, re.DOTALL)
        if "Award winner" in button
    )
    close_button = next(
        button
        for button in re.findall(r"<button\b[^>]*>", preview.text)
        if 'aria-label="Close"' in button
    )
    assert "autofocus" in award_button
    assert "autofocus" not in close_button

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
    awarded = store.latest_draw(event_id)
    award_message = f"Prize awarded to {awarded['entrant_name']}"
    if awarded["organization"]:
        award_message += f" of {awarded['organization']}"
    assert award_message in award_page.text
    assert "The draw is complete" not in award_page.text
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
    awarded_prize = store.latest_draw(event_id)
    assert (
        f'/events/{event_id}/prizes#prize-{awarded_prize["prize_id"]}'
        in history_page.text
    )
    assert f'datetime="{awarded_prize["created_at"]}"' in history_page.text
    assert "history-time" in history_page.text
    assert awarded_prize["created_at"].endswith("+00:00")
    assert 'class="list-search"' in history_page.text
    assert 'aria-label="Search draws"' in history_page.text
    assert "draws completed" in history_page.text
    assert f'id="prize-{prize_id}"' in prize_page.text


def test_undo_award_confirms_then_clears_history(tmp_path):
    app, store = create_app(tmp_path / "undo-award.sqlite3")
    client = _test_client(app)
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    prize_id = store.add_prize(event_id, "Laptop", "Northwind")
    store.draw(event_id, prize_id, chooser=lambda entrants: entrants[0])

    prizes_page = client.get(f"/events/{event_id}/prizes")
    assert "uk-label-secondary" in prizes_page.text
    assert ">Awarded<" in prizes_page.text
    assert 'aria-label="Undo award"' in prizes_page.text
    assert (
        f'data-confirm-action="/events/{event_id}/prizes/{prize_id}/undo"'
        in prizes_page.text
    )
    assert "data-confirm-title" in prizes_page.text
    assert "Ada Lovelace" in prizes_page.text

    undone = client.post(f"/events/{event_id}/prizes/{prize_id}/undo")
    assert "Award undone. The winner is eligible again." in undone.text
    assert 'class="toast toast-info"' in undone.text
    assert store.draw_history(event_id) == []
    assert store.prizes(event_id)[0]["drawn"] == 0
    assert store.entrants(event_id)[0]["eligible"] == 1
    history = client.get(f"/events/{event_id}/history")
    assert "Completed draws will appear here." in history.text
    assert "Ada Lovelace" not in history.text


def test_rosters_page_twenty_items_at_a_time(tmp_path):
    app, store = create_app(tmp_path / "pages.sqlite3")
    client = _test_client(app)
    event_id = store.create_event("Pages")
    client.get(f"/events/{event_id}")
    for index in range(21):
        store.add_entrant(event_id, f"Person {index:02d}", "Org")
        store.add_prize(event_id, f"Prize {index:02d}", "Sponsor")

    for path in ("entrants", "prizes", "draw"):
        page = client.get(f"/events/{event_id}/{path}").text
        assert "Page 1 of 2" in page
        assert 'aria-label="First page"' in page
        assert 'aria-label="Previous page"' in page
        assert 'aria-label="Next page"' in page
        assert 'aria-label="Last page"' in page
        items = re.findall(r"<li\b[^>]*>", page)
        assert len(items) == 21
        assert sum("hidden" in item for item in items) == 1


def test_empty_history_page_does_not_offer_start_draw_link(tmp_path):
    app, store = create_app(tmp_path / "empty-history.sqlite3")
    event_id = store.create_event("Awards")
    client = _test_client(app)

    page = client.get(f"/events/{event_id}/history").text

    assert "uk-placeholder" in page
    assert "Completed draws will appear here." in page
    assert "Start a draw" not in page


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
    assert 'aria-label="Remove"' in edited_entrant.text
    assert 'aria-label="Edit"' in edited_entrant.text
    assert "Confirm eligibility" in edited_entrant.text
    assert ">Eligible<" in edited_entrant.text
    ineligible = client.post(
        f"/events/{event_id}/entrants/{entrant_id}/eligible",
        data={"eligible": "0"},
    )
    assert "Entrant eligibility updated." in ineligible.text
    assert store.entrants(event_id)[0]["eligible"] == 0
    client.post(f"/events/{event_id}/entrants/{entrant_id}/remove")
    assert store.entrants(event_id) == []

    added_prize = client.post(
        f"/events/{event_id}/prizes",
        data={"name": "Laptop", "sponsor": "Northwind", "prize_number": "12"},
    )
    assert "#12" in added_prize.text
    prize_id = store.prizes(event_id)[0]["id"]
    assert store.prizes(event_id)[0]["prize_number"] == 12
    edited_prize = client.post(
        f"/events/{event_id}/prizes/{prize_id}/edit",
        data={"name": "Tablet", "sponsor": "Contoso", "prize_number": ""},
    )
    assert "Tablet" in edited_prize.text
    assert "#12" not in edited_prize.text
    assert store.prizes(event_id)[0]["sponsor"] == "Contoso"
    assert store.prizes(event_id)[0]["prize_number"] is None
    client.post(f"/events/{event_id}/prizes/{prize_id}/remove")
    assert store.prizes(event_id) == []


def test_toasts_use_the_palette_for_each_tone(tmp_path):
    app, store = create_app(tmp_path / "toast-tones.sqlite3")
    client = _test_client(app)
    event_id = store.create_event("Awards")

    info = client.get(f"/events/{event_id}?status=settings-updated")
    warning = client.get(f"/events/{event_id}?status=no-file")
    error = client.get(f"/events/{event_id}/prizes?status=invalid-prize")

    assert 'class="toast toast-info"' in info.text
    assert "fastprize-scroll" in info.text
    assert "Winner eligibility setting updated." in info.text
    assert 'class="toast toast-warning"' in warning.text
    assert "Choose a CSV file to import." in warning.text
    assert 'class="toast toast-error"' in error.text
    assert "Prize name is required." in error.text


def test_home_desk_status_reports_missing_entrants_or_prizes(tmp_path):
    app, store = create_app(tmp_path / "desk.sqlite3")
    client = _test_client(app)
    event_id = store.create_event("Awards")
    client.get(f"/events/{event_id}")

    empty_home = client.get("/")
    assert "This event has no entrants or prizes yet." in empty_home.text

    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    entrants_only = client.get("/")
    assert "This event has no prizes yet." in entrants_only.text
    assert "Your draw desk is ready." not in entrants_only.text

    store.add_prize(event_id, "Laptop", "Northwind")
    ready_home = client.get("/")
    assert "Your draw desk is ready." in ready_home.text

    store.remove_entrant(event_id, store.entrants(event_id)[0]["id"])
    prizes_only = client.get("/")
    assert "This event has no entrants yet." in prizes_only.text


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

    manage_page = client.get(f"/events/{event_id}").text
    assert 'data-confirm-choices="clear"' in manage_page
    assert 'data-confirm-label="Confirm"' in manage_page
    assert 'name="clear_entrants"' in manage_page
    assert 'name="clear_prizes"' in manage_page
    assert 'name="clear_history"' in manage_page

    unchanged = client.post(f"/events/{event_id}/clear-data")
    assert "Choose entrants, prizes, or history to clear." in unchanged.text
    assert len(store.entrants(event_id)) == 2
    assert len(store.prizes(event_id)) == 2

    reset_page = client.post(
        f"/events/{event_id}/clear-data",
        data={"clear_entrants": "1", "clear_prizes": "1"},
    )
    assert "Cleared entrants and prizes." in reset_page.text
    assert store.entrants(event_id) == []
    assert store.prizes(event_id) == []


def test_operator_can_delete_an_event(tmp_path):
    app, store = create_app(tmp_path / "delete-event.sqlite3")
    client = _test_client(app)
    kept_id = store.create_event("Keep")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    laptop = store.add_prize(event_id, "Laptop", "Northwind")
    store.draw(event_id, laptop, chooser=lambda entrants: entrants[0])
    travel = store.add_prize(event_id, "Travel", "Contoso")
    store.save_preview(
        event_id,
        travel,
        {"id": None, "name": "Grace Hopper", "organization": "Naval Lab"},
        {"prize_name": "Travel", "sponsor": "Contoso"},
    )

    manage_page = client.get(f"/events/{event_id}")
    assert "Live Display" not in manage_page.text
    assert f'data-confirm-action="/events/{event_id}/delete"' in manage_page.text
    assert 'data-confirm-choices="delete"' in manage_page.text
    assert 'name="delete_event"' in manage_page.text
    assert "&lt;strong&gt;Awards&lt;/strong&gt;" in manage_page.text
    assert 'class="dialog-title"' in manage_page.text
    assert "Delete event" in manage_page.text

    kept = client.post(f"/events/{event_id}/delete")
    assert "Check the box to delete this event and all of its data." in kept.text
    assert store.get_event(event_id) is not None
    assert store.entrants(event_id)
    assert store.draw_history(event_id)

    events_page = client.post(
        f"/events/{event_id}/delete",
        data={"delete_event": "1"},
    )
    assert events_page.status_code == 200
    assert "Awards" not in events_page.text
    assert "Keep" in events_page.text
    assert store.get_event(event_id) is None
    assert store.entrants(event_id) == []
    assert store.prizes(event_id) == []
    assert store.draw_history(event_id) == []
    assert store.latest_preview(event_id) is None
    assert client.cli.cookies.get("fastprize_event_id") is None
    assert "Awards" not in client.get("/").text
    assert store.get_event(kept_id) is not None


def test_live_display_button_shares_a_slug_link(tmp_path):
    app, store = create_app(tmp_path / "display-slug.sqlite3")
    client = _test_client(app)
    event_id = store.create_event("Launch Day")
    duplicate_id = store.create_event("Launch day")
    assert store.display_slug(store.get_event(event_id)) == "launch_day"
    assert (
        store.display_slug(store.get_event(duplicate_id))
        == f"launch_day_{duplicate_id}"
    )
    client.get(f"/events/{event_id}")

    home = client.get("/")
    assert 'onclick="openDisplayLink()"' in home.text
    assert f'href="/events/{event_id}/display"' not in home.text
    assert 'id="display-link"' in home.text

    link = client.get(f"/events/{event_id}/display-link")
    assert link.status_code == 200
    assert '<svg viewBox="' in link.text
    assert "/launch_day<" in link.text or "/launch_day\"" in link.text
    assert f"launch_day_{duplicate_id}" not in link.text

    guest = _test_client(app, login=False)
    display = guest.get("/launch_day")
    assert display.status_code == 200
    assert "The next name could be yours." in display.text
    assert guest.get("/launch_day/latest").status_code == 200
    assert guest.get(f"/events/{event_id}/display").status_code == 200
    private = guest.get(f"/events/{event_id}/display-link")
    assert "Open this link on the projector" not in private.text


def test_management_requires_sign_in_and_projector_stays_public(tmp_path):
    app, store = create_app(tmp_path / "auth-public.sqlite3")
    client = _test_client(app, login=False)
    event_id = store.create_event("Awards")

    home = client.get("/")
    assert "Admin setup required" in home.text
    assert "uv run fastprize-admin create you@example.com" in home.text
    assert 'href="/events"' not in home.text

    display = client.get(f"/events/{event_id}/display")
    assert display.status_code == 200
    assert "Live draw" in display.text
    assert 'class="brand-mark"' in display.text
    assert client.get(f"/events/{event_id}/display/latest").status_code == 200


def test_live_display_replaces_expired_winner_with_stable_quote():
    from datetime import UTC, datetime, timedelta

    from fasthtml.common import to_xml

    assert TECHNOLOGY_QUOTES
    now = datetime.now(UTC)
    draw = {
        "id": 42,
        "entrant_name": "Ada Lovelace",
        "organization": "Engine Co",
        "prize_name": "Laptop",
        "sponsor": "Northwind",
        "created_at": (now - timedelta(minutes=3, seconds=10)).isoformat(),
    }
    first = to_xml(winner_fragment(draw))
    second = to_xml(winner_fragment(draw))
    later = to_xml(
        winner_fragment(
            {
                **draw,
                "created_at": (now - timedelta(minutes=6, seconds=10)).isoformat(),
            }
        )
    )
    selected = next(quote for quote in TECHNOLOGY_QUOTES if quote in first)
    assert f'"{selected}"' in first
    assert "live-quote" in first
    assert 'data-display-state="quote"' in first
    assert "Ada Lovelace" not in first
    assert first == second
    assert first != later


def test_admin_can_sign_in_and_add_another_account(tmp_path):
    app, store = create_app(tmp_path / "auth-accounts.sqlite3")
    client = _test_client(app)
    accounts = client.get("/admin/accounts")
    assert accounts.status_code == 200
    assert "test-admin@example.test" in accounts.text
    assert "total," not in accounts.text
    assert "md:grid-cols-2" in accounts.text
    created = client.post(
        "/admin/accounts",
        data={"email": "second@example.test", "password": "second-admin-password"},
    )
    assert "Admin account created." in created.text
    second = store.get_admin_by_email("second@example.test")
    assert second is not None
    assert "admin-enabled-" in created.text
    assert 'aria-label="Delete"' in created.text
    assert ">Disable<" not in created.text
    disabled = client.post(
        f"/admin/accounts/{second['id']}/enabled",
        data={"enabled": "0"},
    )
    assert "Admin account disabled." in disabled.text
    assert "Disabled" in disabled.text
    assert store.get_admin(second["id"])["enabled"] == 0
    enabled = client.post(
        f"/admin/accounts/{second['id']}/enabled",
        data={"enabled": ["0", "1"]},
    )
    assert "Admin account enabled." in enabled.text
    assert store.get_admin(second["id"])["enabled"] == 1
    signed_out = client.post("/logout")
    assert "Admin sign in" in signed_out.text
