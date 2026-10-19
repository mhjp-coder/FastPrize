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

    assert f'href="/events/{first_id}/entrants"' not in client.get("/").text

    first_selection = client.get(f"/events/{first_id}")
    assert first_selection.cookies.get("fastprize_event_id") == str(first_id)
    first_home = client.get("/")
    assert "First event" in first_home.text
    assert f'href="/events/{first_id}/entrants"' in first_home.text
    assert f'href="/events/{second_id}/entrants"' not in first_home.text

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
    assert "No folded slips." in home.text
    assert 'href="/events"' in home.text
    assert "Create event" not in home.text
    assert "/assets/vendor/franken.css" in home.text
    assert "/assets/vendor/tailwind.js" in home.text
    assert "/assets/app.css" in home.text
    assert "beercss" not in home.text
    assert 'class="bg-background text-foreground"' in home.text
    assert "uk-theme-slate" in home.text
    assert "uk-theme-blue" in home.text
    assert "uk-theme-green" in home.text
    assert "uk-theme-rose" in home.text
    assert "uk-theme-yellow" in home.text
    assert "uk-theme-zinc" not in home.text
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
    assert "Import selected files" in manage_page.text
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

    client.post(f"/events/{event_id}/settings", data={"remove_winners": "0"})
    assert store.get_event(event_id)["remove_winners"] == 0

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

    reset_page = client.post(f"/events/{event_id}/clear-data")
    assert "Cleared all entrants and prizes." in reset_page.text
    assert store.entrants(event_id) == []
    assert store.prizes(event_id) == []


def test_operator_can_delete_an_event(tmp_path):
    app, store = create_app(tmp_path / "delete-event.sqlite3")
    client = _test_client(app)
    kept_id = store.create_event("Keep")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    store.add_prize(event_id, "Laptop", "Northwind")

    manage_page = client.get(f"/events/{event_id}")
    assert "Live Display" not in manage_page.text
    assert f'data-confirm-action="/events/{event_id}/delete"' in manage_page.text
    assert "Delete event" in manage_page.text

    events_page = client.post(f"/events/{event_id}/delete")
    assert events_page.status_code == 200
    assert "Awards" not in events_page.text
    assert "Keep" in events_page.text
    assert store.get_event(event_id) is None
    assert store.entrants(event_id) == []
    assert store.prizes(event_id) == []
    assert client.cli.cookies.get("fastprize_event_id") is None
    assert "Awards" not in client.get("/").text
    assert store.get_event(kept_id) is not None


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
    assert 'id="admin-counts"' in accounts.text
    created = client.post(
        "/admin/accounts",
        data={"email": "second@example.test", "password": "second-admin-password"},
    )
    assert "Admin account created." in created.text
    assert store.get_admin_by_email("second@example.test") is not None
    signed_out = client.post("/logout")
    assert "Admin sign in" in signed_out.text
