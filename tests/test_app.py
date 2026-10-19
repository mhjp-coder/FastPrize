import re
import sys
import time
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, cast

import pytest
from fasthtml.common import Client, to_xml

from fastprize import auth_cli
from fastprize.app import create_app
from fastprize.auth import hash_password, verify_password
from fastprize.store import DEFAULT_DATABASE_PATH, PrizeDrawStore, get_database_path
from fastprize.ui import TECHNOLOGY_QUOTES, winner_fragment


def test_default_database_path_is_project_root(tmp_path, monkeypatch):
    monkeypatch.delenv("FASTPRIZE_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    assert (
        get_database_path() == Path(__file__).resolve().parents[1] / "fastprize.sqlite3"
    )
    assert get_database_path() == DEFAULT_DATABASE_PATH


@pytest.mark.parametrize("entrypoint", ["app", "cli"])
@pytest.mark.parametrize("environment_override", [False, True])
def test_database_entrypoints_ignore_working_directory(
    tmp_path, monkeypatch, entrypoint, environment_override
):
    root_database = tmp_path / "fastprize.sqlite3"
    override_database = tmp_path / "override.sqlite3"
    working_directory = tmp_path / "nested"
    working_directory.mkdir()
    monkeypatch.chdir(working_directory)
    monkeypatch.setattr("fastprize.store.DEFAULT_DATABASE_PATH", root_database)
    monkeypatch.delenv("FASTPRIZE_DB_PATH", raising=False)
    expected_database = root_database
    if environment_override:
        monkeypatch.setenv("FASTPRIZE_DB_PATH", str(override_database))
        expected_database = override_database

    if entrypoint == "app":
        _, store = create_app()
        assert store.db_path == str(expected_database)
    else:
        monkeypatch.setattr(
            sys, "argv", ["fastprize-admin", "create", "admin@example.test"]
        )
        monkeypatch.setattr(
            auth_cli.getpass, "getpass", lambda prompt: "test-password-123"
        )
        auth_cli.main()
        assert PrizeDrawStore(expected_database).get_admin_by_email(
            "admin@example.test"
        )

    assert expected_database.exists()
    assert not (working_directory / "fastprize.sqlite3").exists()


@pytest.mark.parametrize(
    ("enabled", "new_password"),
    [(False, "new-password-123"), (True, "new-password-123"), (False, "short")],
)
def test_cli_password_reset_reenables_account(
    tmp_path, monkeypatch, enabled, new_password
):
    database = tmp_path / "cli-reset.sqlite3"
    store = PrizeDrawStore(database)
    admin = store.create_admin("admin@example.test", hash_password("old-password-123"))
    store.db.t.admins.update({"id": admin["id"], "enabled": int(enabled)})
    monkeypatch.setenv("FASTPRIZE_DB_PATH", str(database))
    monkeypatch.setattr(
        sys, "argv", ["fastprize-admin", "reset-password", admin["email"]]
    )
    monkeypatch.setattr(auth_cli.getpass, "getpass", lambda prompt: new_password)

    if len(new_password) < 12:
        with pytest.raises(SystemExit):
            auth_cli.main()
        unchanged = store.get_admin(admin["id"])
        assert unchanged is not None
        assert not unchanged["enabled"]
        assert unchanged["password_hash"] == admin["password_hash"]
        assert unchanged["auth_version"] == admin["auth_version"]
    else:
        auth_cli.main()
        updated = store.get_admin(admin["id"])
        assert updated is not None
        assert updated["enabled"]
        assert verify_password(updated["password_hash"], new_password)
        assert not verify_password(updated["password_hash"], "old-password-123")
        assert updated["auth_version"] > admin["auth_version"]


def _test_client(app):
    client = Client(app)
    cast(Any, client).cli.follow_redirects = True
    cast(Any, client).cli.headers.update({"Origin": "http://testserver"})
    store = app.state.store
    if store.get_admin_by_email("test-admin@example.test") is None:
        store.create_admin(
            "test-admin@example.test", hash_password("test-password-123")
        )
    login_page = client.get("/login").text
    csrf_token = re.search(r'name="csrf" value="([^"]+)"', login_page)
    assert csrf_token is not None
    client.post(
        "/login",
        data={
            "email": "test-admin@example.test",
            "password": "test-password-123",
            "csrf": csrf_token.group(1),
        },
    )
    return client


def test_theme_controls_are_placed_in_responsive_navigation(tmp_path):
    app, _ = create_app(tmp_path / "responsive-theme-controls.sqlite3")
    page = _test_client(app).get("/").text
    desktop_nav = re.search(r'<nav class="left drawer[^"]*">.*?</nav>', page, re.DOTALL)
    mobile_nav = re.search(
        r'<nav class="top s padding horizontal middle-align">.*?</nav>',
        page,
        re.DOTALL,
    )

    assert desktop_nav is not None
    assert mobile_nav is not None
    assert 'id="theme-controls-desktop"' in desktop_nav.group()
    assert 'id="theme-controls-mobile"' in mobile_nav.group()
    assert 'data-theme-mode="toggle"' in desktop_nav.group()
    assert 'data-theme-mode="toggle"' in mobile_nav.group()
    assert 'data-theme-mode-icon="true"' in desktop_nav.group()
    assert 'data-theme-mode-icon="true"' in mobile_nav.group()
    assert 'data-theme-picker-open="true"' in desktop_nav.group()
    assert 'data-theme-picker-open="true"' in mobile_nav.group()
    assert (
        'class="horizontal middle-align small-space small-margin"'
        in desktop_nav.group()
    )
    assert 'class="horizontal middle-align small-space"' in mobile_nav.group()


@pytest.mark.parametrize("selected_event", [False, True])
def test_desktop_and_mobile_navigation_follow_the_same_order(tmp_path, selected_event):
    app, store = create_app(tmp_path / "menu-order.sqlite3")
    client = _test_client(app)
    if selected_event:
        event_id = store.create_event("Awards")
        client.get(f"/events/{event_id}")
    page = client.get("/admin/accounts").text
    desktop = re.search(r'<nav class="left drawer[^\"]*">.*?</nav>', page, re.DOTALL)
    mobile = re.search(r"<footer\b[^>]*>.*?</footer>", page, re.DOTALL)
    assert desktop is not None
    assert mobile is not None
    expected = ["Events", "Admin"]
    if selected_event:
        expected = [
            "Draw",
            "Live Display",
            "Entrants",
            "Prizes",
            "Draw History",
            "Manage",
            "Events",
            "Admin",
        ]
        for navigation in (desktop.group(), mobile.group()):
            assert f'hx-get="/events/{event_id}/display-link"' in navigation
            assert 'hx-target="#display-link-modal"' in navigation
    assert re.findall(r"<div>([^<]+)</div>", desktop.group()) == expected
    assert re.findall(r'<a\b[^>]*title="([^"]+)"', mobile.group()) == expected


def test_event_links_have_individual_compact_containers(tmp_path):
    app, store = create_app(tmp_path / "event-links.sqlite3")
    store.create_event("Awards")
    store.create_event("Raffle")

    page = _test_client(app).get("/events").text

    assert (
        page.count(
            'class="s12 m6 l4 link responsive center-align padding surface-container small-round"'
        )
        == 2
    )
    assert '<h3 class="small">Awards</h3>' in page
    assert '<h3 class="small">Raffle</h3>' in page


def test_events_page_highlights_selected_active_event(tmp_path):
    app, store = create_app(tmp_path / "active-event-highlight.sqlite3")
    active_id = store.create_event("Awards")
    other_id = store.create_event("Raffle")
    client = _test_client(app)

    client.get(f"/events/{active_id}")
    page = client.get("/events").text

    active_link = re.search(
        rf'<a href="/events/{active_id}"[^>]*class="[^"]*link responsive[^"]*"[^>]*>.*?</a>',
        page,
        re.DOTALL,
    )
    other_link = re.search(
        rf'<a href="/events/{other_id}"[^>]*class="[^"]*link responsive[^"]*"[^>]*>.*?</a>',
        page,
        re.DOTALL,
    )
    assert active_link is not None
    assert other_link is not None
    assert 'aria-current="true"' in active_link.group()
    assert "primary-container" in active_link.group()
    assert "CURRENT EVENT" not in active_link.group()
    assert 'aria-current="true"' not in other_link.group()
    assert "surface-container" in other_link.group()


def test_events_create_form_stacks_on_small_screens(tmp_path):
    app, _ = create_app(tmp_path / "responsive-event-form.sqlite3")
    page = _test_client(app).get("/events").text

    assert 'class="s12 m7 field label border fill round extra"' in page
    assert 'class="s12 m5 responsive extra primary"' in page


def test_entrant_add_section_is_a_closed_expansion(tmp_path):
    app, store = create_app(tmp_path / "entrant-add-expansion.sqlite3")
    event_id = store.create_event("Awards")

    page = _test_client(app).get(f"/events/{event_id}/entrants").text
    details_tag = re.search(r'<details\b[^>]*id="entrant-add-expansion"[^>]*>', page)

    assert details_tag is not None
    assert "open" not in details_tag.group()
    assert 'class="button primary responsive none"' in page
    assert 'aria-expanded="false"' in page
    assert "data-add-expansion-chevron" in page
    assert ">expand_more</i>" in page
    assert 'id="entrant-name"' in page


def test_entrants_page_matches_management_card_layout(tmp_path):
    app, store = create_app(tmp_path / "entrant-page-layout.sqlite3")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    client = _test_client(app)
    page = client.get(f"/events/{event_id}/entrants").text
    entrant_id = store.entrants(event_id)[0]["id"]

    assert (
        'class="card padding primary-container small-round vertical bottom-margin"'
        in page
    )
    assert (
        page.count(
            'class="card padding secondary-container small-round vertical bottom-padding"'
        )
        == 2
    )
    assert page.count('class="s6 m6 l6 field label border fill round extra"') == 2
    assert 'class="s12 responsive extra primary"' in page
    assert (
        'class="s12 m12 l6 card padding tertiary-container small-round vertical"'
        in page
    )
    assert 'aria-label="Remove Ada Lovelace"' in page
    assert 'aria-label="Edit Ada Lovelace"' in page
    assert "<i>edit</i>" in page
    assert 'class="button circle primary"' in page
    assert f'data-edit-target="entrant-info-{entrant_id}"' in page
    assert page.count(f'data-hide-while-editing="entrant-info-{entrant_id}"') == 2
    assert f'hx-get="/events/{event_id}/entrants/{entrant_id}/edit"' in page
    assert f'hx-target="#entrant-info-{entrant_id}"' in page
    assert (
        'class="horizontal middle-align small-space top-margin right-align bottom-margin"'
        in page
    )
    assert "style=" not in page
    assert "<i>delete</i><span>Remove</span>" in page
    assert 'aria-label="Organization (optional)"' in page

    edit_form = client.get(f"/events/{event_id}/entrants/{entrant_id}/edit").text
    assert "style=" not in edit_form
    assert edit_form.count('class="field round fill border"') == 2
    assert 'class="circle primary"' in edit_form
    assert 'class="circle"' in edit_form
    assert 'name="name" value="Ada Lovelace"' in edit_form
    assert 'name="organization" value="Engine Co"' in edit_form
    assert "data-inline-edit" in edit_form
    assert f'hx-get="/events/{event_id}/entrants/{entrant_id}/display"' in edit_form

    display = client.get(f"/events/{event_id}/entrants/{entrant_id}/display").text
    assert "<strong>Ada Lovelace</strong>" in display
    assert "<small>Engine Co</small>" in display


def test_entrant_search_filters_names_and_organizations(tmp_path):
    app, store = create_app(tmp_path / "entrant-search.sqlite3")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    store.add_entrant(event_id, "Grace Hopper", "Acme")
    client = _test_client(app)

    page = client.get(f"/events/{event_id}/entrants").text
    assert 'id="entrant-search"' in page
    assert 'class="s12 m6 field large prefix round fill border active"' in page
    assert f'hx-get="/events/{event_id}/entrants/search"' in page
    assert 'hx-target="#entrant-list"' in page

    by_name = client.get(f"/events/{event_id}/entrants/search?search=GRACE").text
    assert "Grace Hopper" in by_name
    assert "Ada Lovelace" not in by_name

    by_organization = client.get(
        f"/events/{event_id}/entrants/search?search=engine"
    ).text
    assert "Ada Lovelace" in by_organization
    assert "Grace Hopper" not in by_organization

    no_matches = client.get(f"/events/{event_id}/entrants/search?search=missing").text
    assert "No entrants match your search." in no_matches
    assert (
        '<p class="s12 secondary-text">No entrants match your search.</p>' in no_matches
    )
    assert "Ada Lovelace" not in no_matches


def test_entrant_eligibility_button_toggles_status(tmp_path):
    app, store = create_app(tmp_path / "entrant-eligibility-toggle.sqlite3")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace")
    entrant_id = store.entrants(event_id)[0]["id"]
    client = _test_client(app)

    page = client.get(f"/events/{event_id}/entrants").text
    eligibility_dialog = f"eligibility-dialog-{entrant_id}"
    assert "Eligible" in page
    assert 'aria-pressed="true"' in page
    assert 'class="primary">Eligible</button>' in page
    assert f'id="{eligibility_dialog}"' in page
    assert f'aria-controls="{eligibility_dialog}"' in page
    assert "Mark Ada Lovelace not eligible?" in page

    page = client.post(
        f"/events/{event_id}/entrants/{entrant_id}/toggle-eligibility"
    ).text
    assert "Not eligible" in page
    assert 'aria-pressed="false"' in page
    assert 'class="error">Not eligible</button>' in page
    assert "Mark Ada Lovelace eligible?" in page
    assert store.entrants(event_id)[0]["eligible"] == 0

    page = client.post(
        f"/events/{event_id}/entrants/{entrant_id}/toggle-eligibility"
    ).text
    assert "Eligible" in page
    assert "Mark Ada Lovelace not eligible?" in page
    assert store.entrants(event_id)[0]["eligible"] == 1


def test_entrant_mutations_return_htmx_fragments(tmp_path):
    app, store = create_app(tmp_path / "entrant-htmx.sqlite3")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    entrant_id = store.entrants(event_id)[0]["id"]
    client = _test_client(app)
    headers = {"HX-Request": "true"}

    page = client.get(f"/events/{event_id}/entrants").text
    assert (
        f'hx-post="/events/{event_id}/entrants/{entrant_id}/toggle-eligibility"' in page
    )
    assert f'hx-post="/events/{event_id}/entrants/{entrant_id}/remove"' in page
    entrant_dialog = f"remove-entrant-dialog-{entrant_id}"
    assert f'id="{entrant_dialog}"' in page
    assert 'class="modal padding medium-width left-align"' in page
    assert 'aria-label="Confirm removing Ada Lovelace"' in page
    assert f'aria-controls="{entrant_dialog}"' in page
    assert page.count(f'data-ui="#{entrant_dialog}"') == 2
    assert f'action="/events/{event_id}/entrants/{entrant_id}/remove"' in page

    eligibility = client.post(
        f"/events/{event_id}/entrants/{entrant_id}/toggle-eligibility",
        headers=headers,
    )
    assert "<!doctype html>" not in eligibility.text
    assert 'id="entrant-row-' in eligibility.text
    assert 'aria-pressed="false"' in eligibility.text
    assert 'hx-swap-oob="outerHTML"' in eligibility.text
    assert "1 total | 0 eligible" in eligibility.text

    edit_form = client.get(f"/events/{event_id}/entrants/{entrant_id}/edit").text
    assert f'hx-post="/events/{event_id}/entrants/{entrant_id}/edit"' in edit_form
    edited = client.post(
        f"/events/{event_id}/entrants/{entrant_id}/edit",
        data={"name": "Ada Byron", "organization": "Analytical Engines"},
        headers=headers,
    )
    assert "<!doctype html>" not in edited.text
    assert 'id="entrant-row-' in edited.text
    assert "Ada Byron" in edited.text

    removed = client.post(
        f"/events/{event_id}/entrants/{entrant_id}/remove",
        headers=headers,
    )
    assert "<!doctype html>" not in removed.text
    assert 'hx-swap-oob="outerHTML"' in removed.text
    assert "0 total | 0 eligible" in removed.text
    assert store.entrants(event_id) == []


def test_workspace_data_management_uses_confirmation_dialogs(tmp_path):
    app, store = create_app(tmp_path / "data-management-dialogs.sqlite3")
    event_id = store.create_event("Awards")
    page = _test_client(app).get(f"/events/{event_id}").text

    assert "Clear Database" in page
    assert 'id="clear-database-dialog"' in page
    assert page.count('class="modal padding medium-width"') == 2
    assert 'aria-label="Confirm clearing event data"' in page
    assert page.count('data-ui="#clear-database-dialog"') == 2
    assert f'action="/events/{event_id}/clear-data"' in page
    assert 'id="delete-event-dialog"' in page
    assert 'aria-label="Confirm deleting this event"' in page
    assert page.count('data-ui="#delete-event-dialog"') == 2
    assert f'action="/events/{event_id}/delete"' in page
    assert "closest('dialog').close()" not in page
    assert 'onsubmit="return confirm(' not in page


def test_workspace_contains_combined_csv_import_form(tmp_path):
    app, store = create_app(tmp_path / "workspace-import-form.sqlite3")
    event_id = store.create_event("Awards")
    client = _test_client(app)

    workspace = client.get(f"/events/{event_id}").text

    assert 'id="csv-import"' in workspace
    assert workspace.index('<h2 class="small">Prizes</h2>') < workspace.index(
        'id="csv-import"'
    )
    assert 'data-add-expansion="true"' in workspace
    assert 'aria-expanded="false"' in workspace
    assert 'class="button primary responsive none"' in workspace
    assert "<span>Import CSV</span>" in workspace
    assert 'class="s12 vertical"' in workspace
    assert f'action="/events/{event_id}/import"' in workspace
    assert workspace.count('type="file"') == 2
    assert 'for="entrants-file"' in workspace
    assert 'for="prizes-file"' in workspace
    assert 'data-filename-target="entrants-file-name"' in workspace
    assert 'data-filename-target="prizes-file-name"' in workspace
    assert 'aria-controls="entrants-csv-info"' in workspace
    assert 'aria-controls="prizes-csv-info"' in workspace
    assert 'id="entrants-csv-info"' in workspace
    assert 'id="prizes-csv-info"' in workspace
    for dialog_id in ("entrants-csv-info", "prizes-csv-info"):
        dialog = re.search(rf'<dialog\b[^>]*id="{dialog_id}"[^>]*>', workspace)
        assert dialog is not None
        assert 'data-close-on-backdrop="true"' in dialog.group()
    assert "Required: name. Optional: organization." in workspace
    assert (
        "Required: prize_name. Optional: sponsor, number (or prize_number)."
        in workspace
    )
    assert f'href="/events/{event_id}/import"' not in workspace
    assert workspace.count('<h3 class="small">') >= 2
    assert workspace.count('class="circle transparent"') >= 2
    assert (
        workspace.count('class="horizontal middle-align small-space bottom-margin"')
        == 2
    )
    assert 'class="center-align"' not in workspace
    import_form = workspace.split('id="csv-import"', 1)[1]
    assert (
        f'<form enctype="multipart/form-data" action="/events/{event_id}/import" method="post" class="grid small-space">'
        in import_form
    )
    assert '<button type="submit" class="s12 responsive extra primary">' in import_form

    import_alias = client.get(f"/events/{event_id}/import")
    assert import_alias.status_code == 200
    assert 'id="csv-import"' in import_alias.text

    imported = client.post(
        f"/events/{event_id}/import",
        files={
            "entrants_file": ("entrants.csv", "name\nAda Lovelace\n"),
            "prizes_file": ("prizes.csv", "prize_name\nLaptop\n"),
        },
    )
    assert "Imported 1 entrant and 1 prize" in imported.text
    assert len(store.entrants(event_id)) == 1
    assert len(store.prizes(event_id)) == 1


def test_draw_center_shows_create_button_only_when_no_events(tmp_path):
    app, store = create_app(tmp_path / "empty-home.sqlite3")
    client = _test_client(app)

    empty_home = client.get("/").text
    assert (
        "Choose an event to open its workspace, or create one to get started."
        in empty_home
    )
    assert (
        'class="card padding primary-container small-round vertical bottom-margin"'
        in empty_home
    )
    assert (
        empty_home.index("Draw Center")
        < empty_home.index("Hats are for pulling rabbits")
        < empty_home.index("Choose an event to open its workspace")
    )
    assert (
        '<a href="/events" class="button primary responsive extra bottom-margin">'
        in empty_home
    )
    assert "<i>add</i><span>Create event</span>" in empty_home

    store.create_event("Awards")
    populated_home = client.get("/").text
    assert (
        "Choose an event to open its workspace, or create one to get started."
        in populated_home
    )
    assert (
        '<a href="/events" class="button primary responsive extra bottom-margin">'
        not in populated_home
    )


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
    assert 'class="tertiary m6 responsive extra"' in first_home.text
    assert "<i>upload_file</i><span>Import CSV</span>" in first_home.text
    assert "<i>qr_code_2</i><span>Live display</span>" in first_home.text
    assert "Public display" not in first_home.text
    assert "Open projector display" not in first_home.text
    assert f'hx-get="/events/{first_id}/display-link"' in first_home.text
    assert 'hx-target="#display-link-modal"' in first_home.text
    assert 'id="display-link-modal"' in first_home.text
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
    assert home.count('<h2 class="small">1</h2>') == 2

    second_event_id = store.create_event("Raffle")
    store.add_prize(second_event_id, "Headphones")
    client.get(f"/events/{second_event_id}")
    home = client.get("/").text
    assert "Add eligible entrants to get started." in home
    assert f'href="/events/{second_event_id}/import" class="button primary' in home


def test_draw_page_uses_live_draw_prize_cards(tmp_path):
    app, store = create_app(tmp_path / "draw-page-layout.sqlite3")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    entrant_id = store.entrants(event_id)[0]["id"]
    first_prize_id = store.add_prize(event_id, "Laptop", "Northwind", "0007")
    second_prize_id = store.add_prize(event_id, "Coffee basket", "Contoso")
    client = _test_client(app)
    page = client.get(f"/events/{event_id}/draw").text

    assert '<h1 class="small max">Live Draw</h1>' in page
    assert '<p class="s9">Awards</p>' in page
    assert 'class="s3 right-align">2 prizes left</span>' in page
    assert page.index("Live Draw</h1>") < page.index('<p class="s9">Awards</p>')
    assert page.index("Live Draw</h1>") < page.index("Live display</span>")
    assert 'title="Live display"' in page
    assert 'aria-label="Live display"' in page
    assert f'hx-get="/events/{event_id}/display-link"' in page
    assert 'hx-target="#display-link-modal"' in page
    assert f'href="/events/{event_id}/display"' not in page
    assert 'id="display-link-modal"' in page
    assert 'id="draw-prize-search"' in page
    assert f'hx-get="/events/{event_id}/draw/search"' in page
    assert 'hx-target="#draw-prize-list"' in page
    assert page.index("<div>Draw</div>") < page.index("<div>Live Display</div>")
    assert page.index("<div>Live Display</div>") < page.index("<div>Draw History</div>")

    link = client.get(f"/events/{event_id}/display-link").text
    assert '<h2 class="small">Live display</h2>' in link
    assert 'id="display-link-dialog"' in link
    assert 'data-close-on-backdrop="true"' in link
    assert 'class="modal padding medium-width left-align"' in link
    assert 'data-auto-open="true"' in link
    assert f'href="http://testserver/events/{event_id}/display"' in link
    assert 'src="data:image/svg+xml' in link
    assert 'alt="QR code for the live draw display link"' in link
    assert 'method="dialog"' in link
    assert client.get("/events/999/display-link").status_code == 404
    assert "Add an eligible entrant before starting a draw." not in page
    assert "Draw a prize" not in page
    assert "1 eligible entrants" not in page
    assert (
        page.count(
            'class="s12 m12 l6 card padding tertiary-container small-round vertical"'
        )
        == 2
    )
    assert page.count("<i>casino</i><span>Draw</span>") == 2
    assert 'class="grid middle-align small-space top-margin bottom-margin"' in page
    assert 'class="s6"># 0007</small>' in page
    assert page.index('class="s6"># 0007</small>') < page.index(
        f'action="/events/{event_id}/draws/{first_prize_id}/preview"'
    )
    assert "style=" not in page
    assert "Select winner" not in page
    assert f'action="/events/{event_id}/draws/{first_prize_id}/preview"' in page
    assert f'action="/events/{event_id}/draws/{second_prize_id}/preview"' in page
    assert 'aria-label="Edit' not in page
    assert 'aria-label="Remove' not in page

    preview = client.get(
        f"/events/{event_id}/draw?preview={first_prize_id}&winner={entrant_id}"
    ).text
    assert "Confirm draw" not in preview
    assert "<h2>Ada Lovelace</h2>" in preview
    assert 'class="large-text secondary-text">Engine Co</p>' in preview
    assert "<h3>Laptop</h3>" in preview
    assert 'class="large-text secondary-text">Northwind</p>' in preview
    assert 'class="extra primary"' in preview
    assert 'class="extra tertiary"' in preview
    assert 'class="extra error"' in preview
    assert 'form="award-draw-form"' in preview
    assert 'form="redraw-draw-form"' in preview
    assert 'form="cancel-draw-form"' in preview
    assert preview.index("Ada Lovelace") < preview.index("Engine Co")
    assert preview.index("Engine Co") < preview.index("Laptop")
    assert preview.index("Laptop") < preview.index("Northwind")
    assert "Cancel" in preview
    assert f'action="/events/{event_id}/draw"' in preview
    assert 'class="modal padding large-width left-align draw-confirmation"' in preview
    assert 'class="wrap small-space m8"' in preview
    assert 'class="right-align m4"' in preview
    assert 'class="wrap small-space top-margin s"' in preview
    assert 'class="large primary"' in preview
    assert 'class="large tertiary"' in preview
    assert 'class="large error"' in preview
    assert "absolute bottom" not in preview
    assert "style=" not in preview
    assert 'id="draw-confirmation"' in preview
    assert 'data-auto-open="true"' in preview
    assert "dialog.draw-confirmation[open]::backdrop" not in preview
    assert (
        preview.index("Award winner")
        < preview.index("Redraw")
        < preview.index("Cancel")
    )


def test_draw_search_filters_prize_names_and_sponsors(tmp_path):
    app, store = create_app(tmp_path / "draw-search.sqlite3")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace")
    store.add_prize(event_id, "Laptop", "Northwind", "001")
    store.add_prize(event_id, "Coffee basket", "Contoso", "002")
    client = _test_client(app)

    by_name = client.get(f"/events/{event_id}/draw/search?search=COFFEE").text
    assert "Coffee basket" in by_name
    assert "Laptop" not in by_name
    assert f'action="/events/{event_id}/draws/2/preview"' in by_name
    assert "# 002" in by_name

    by_sponsor = client.get(f"/events/{event_id}/draw/search?search=northwind").text
    assert "Laptop" in by_sponsor
    assert "Coffee basket" not in by_sponsor

    by_number = client.get(f"/events/{event_id}/draw/search?search=001").text
    assert "Laptop" in by_number
    assert "Coffee basket" not in by_number

    no_matches = client.get(f"/events/{event_id}/draw/search?search=missing").text
    assert "No prizes match your search." in no_matches


def test_draw_page_button_opens_event_management_when_empty(tmp_path):
    app, store = create_app(tmp_path / "empty-draw-page.sqlite3")
    event_id = store.create_event("Awards")

    page = _test_client(app).get(f"/events/{event_id}/draw").text

    assert "No prizes are available to draw." in page
    assert f'action="/events/{event_id}" method="get"' in page
    assert 'type="submit" class="s12 responsive extra primary"' in page
    assert "Manage event" in page
    assert "Add a prize" not in page


def test_empty_entrants_and_prizes_buttons_open_event_management(tmp_path):
    app, store = create_app(tmp_path / "empty-management-pages.sqlite3")
    event_id = store.create_event("Awards")
    client = _test_client(app)

    for section in ("entrants", "prizes"):
        page = client.get(f"/events/{event_id}/{section}").text
        assert "Manage event" in page
        assert f'action="/events/{event_id}" method="get" class="s12"' in page
        assert 'type="submit" class="responsive extra primary"' in page

    assert (
        "Manage event"
        not in client.get(f"/events/{event_id}/entrants/search?search=missing").text
    )
    assert (
        "Manage event"
        not in client.get(f"/events/{event_id}/prizes/search?search=missing").text
    )


def test_awarded_prize_stays_in_draw_list_as_inert_last_item(tmp_path):
    app, store = create_app(tmp_path / "awarded-prize-list.sqlite3")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace")
    awarded_prize_id = store.add_prize(event_id, "Laptop")
    remaining_prize_id = store.add_prize(event_id, "Coffee basket")
    client = _test_client(app)
    client.post(f"/events/{event_id}/draws/{awarded_prize_id}/preview")
    winner_id = store.latest_preview(event_id)["entrant_id"]

    page = client.post(
        f"/events/{event_id}/draws/{awarded_prize_id}/award",
        data={"winner": winner_id},
    ).text

    assert "The draw is complete. The projector is updating now." not in page
    assert 'class="s3 right-align">1 prize left</span>' in page
    assert re.search(r'<button\b[^>]*\bdisabled(?:="")?[^>]*>Awarded</button>', page)
    assert f'action="/events/{event_id}/draws/{awarded_prize_id}/preview"' not in page
    assert page.index("Coffee basket") < page.index("Laptop")
    assert f'action="/events/{event_id}/draws/{remaining_prize_id}/preview"' in page


def test_awarded_prize_can_be_returned_to_pool_from_prizes_page(tmp_path):
    app, store = create_app(tmp_path / "return-prize-to-pool.sqlite3")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace")
    prize_id = store.add_prize(event_id, "Laptop")
    store.draw(event_id, prize_id, chooser=lambda entrants: entrants[0])
    client = _test_client(app)

    page = client.get(f"/events/{event_id}/prizes").text
    dialog_id = f"return-prize-dialog-{prize_id}"
    return_url = f"/events/{event_id}/prizes/{prize_id}/return"
    assert "Return prize to pool?" in page
    assert f'id="{dialog_id}"' in page
    assert f'action="{return_url}"' in page
    assert f'hx-post="{return_url}"' in page
    assert "Awarded to Ada Lovelace" in page
    assert "<strong>Laptop</strong>" in page
    assert "<strong>Ada Lovelace</strong>" in page

    returned = client.post(return_url, headers={"HX-Request": "true"})

    assert "<!doctype html>" not in returned.text
    assert f'id="prize-row-{prize_id}"' in returned.text
    assert f'hx-get="/events/{event_id}/prizes/{prize_id}/edit"' in returned.text
    assert f'hx-post="/events/{event_id}/prizes/{prize_id}/remove"' in returned.text
    assert 'hx-swap-oob="outerHTML"' in returned.text
    assert "1 available | 1 total" in returned.text
    assert store.draw_history(event_id) == []
    assert store.prizes(event_id)[0]["drawn"] == 0
    assert store.entrants(event_id)[0]["eligible"] == 1

    history_page = client.get(f"/events/{event_id}/history").text
    assert "Laptop" not in history_page


def test_empty_history_page_does_not_offer_start_draw_link(tmp_path):
    app, store = create_app(tmp_path / "empty-history.sqlite3")
    event_id = store.create_event("Awards")
    client = _test_client(app)

    page = client.get(f"/events/{event_id}/history").text

    assert "<p>Completed draws will appear here.</p>" in page
    assert "Start a draw" not in page


def test_history_page_uses_striped_table_and_stacks_cell_details(tmp_path):
    app, store = create_app(tmp_path / "history-layout.sqlite3")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    prize_id = store.add_prize(event_id, "Laptop", "Northwind")
    store.draw(event_id, prize_id, chooser=lambda entrants: entrants[0])
    client = _test_client(app)

    page = client.get(f"/events/{event_id}/history").text

    assert '<h1 class="small">Draw history</h1>' in page
    assert "COMPLETED DRAWS" not in page
    assert 'class="stripes"' in page
    assert "<th>Time</th>" in page
    assert "history-timezone" not in page
    assert "Time zone" not in page
    assert "<select" not in page
    assert "Times are stored in UTC." not in page
    draw = store.draw_history(event_id)[0]
    assert f'datetime="{draw["created_at"]}"' in page
    assert 'data-history-time="true"' in page
    assert 'data-history-date="true"' in page
    assert 'data-history-clock="true"' in page
    assert '<br class="s">' in page or '<br class="s" />' in page
    assert draw["created_at"][:10] in page
    assert f"{draw['created_at'][11:16]} UTC" in page
    assert re.search(
        r'<td>\s*<div class="vertical">\s*<strong>Ada Lovelace</strong>'
        r"<small>Engine Co</small>\s*</div>\s*</td>",
        page,
    )
    assert re.search(
        r'<td>\s*<div class="vertical">\s*<strong>Laptop</strong>'
        r"<small>Northwind</small>\s*</div>\s*</td>",
        page,
    )


def test_projector_live_result_uses_htmx_fragment(tmp_path):
    app, store = create_app(tmp_path / "projector-htmx.sqlite3")
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace", "Engine Co")
    prize_id = store.add_prize(event_id, "Laptop", "Northwind")
    client = _test_client(app)

    empty_display = client.get(f"/events/{event_id}/display").text
    assert '<body class="screen">' in empty_display
    assert "fastprize-live-display-velvet-" not in empty_display
    assert "background-image: linear-gradient(135deg" in empty_display
    assert "color-mix(in srgb, var(--surface) 86%, var(--primary) 14%)" in empty_display
    assert "var(--surface) 55%" in empty_display
    assert "@media (max-height: 600px)" in empty_display
    assert "@media (max-height: 480px)" in empty_display
    assert ".live-display-quote" in empty_display
    assert "align-self: center" in empty_display
    assert 'id="live-display-theme-controls"' in empty_display
    assert 'data-add-expansion="true"' in empty_display
    assert 'data-theme-picker-open="true"' in empty_display
    assert 'id="theme-color-picker"' in empty_display
    assert re.search(r'src="/assets/theme\.js\?v=\d+"', empty_display)
    assert 'href="/assets/theme-palette.css?v=3"' in empty_display
    assert empty_display.count('data-theme-palette="') == 4
    assert 'data-theme-palette="sapphire"' in empty_display
    assert "right: calc(100% + .5rem)" in empty_display
    assert 'class="center-align live-display-lead"' in empty_display
    assert "font-size: 5rem" in empty_display

    client.post(f"/events/{event_id}/draws/{prize_id}/preview")

    display = client.get(f"/events/{event_id}/display").text
    assert f'hx-get="/events/{event_id}/display/latest-fragment"' in display
    assert 'hx-trigger="every 1s"' in display
    assert 'class="upper secondary-text center-align live-display-heading"' in display
    assert 'class="secondary-text"' in display
    assert 'class="live-display-footer center-align padding"' in display
    assert 'src="/assets/fastprize-logo.svg"' in display
    assert ">FastPrize</h6>" in display
    assert "FastPrize | Live draw" not in display
    assert 'class="responsive center-align vertical"' in display
    assert 'class="vertical center-align"' in display
    assert "top: 1rem" in display
    fragment = client.get(
        f"/events/{event_id}/display/latest-fragment",
        headers={"HX-Request": "true"},
    ).text
    assert "<!doctype html>" not in fragment
    assert 'id="live-result"' in fragment
    assert 'hx-swap="outerHTML"' in fragment
    assert 'class="center-align live-display-lead"' in fragment
    assert 'data-display-state="winner"' in fragment
    assert "Ada Lovelace" in fragment
    assert ">Engine Co</h6>" in fragment
    assert "<strong>Laptop</strong>" in fragment
    assert "<strong>Northwind</strong>" in fragment


def test_anonymous_projector_is_public_but_management_and_display_link_are_protected(
    tmp_path,
):
    from fasthtml.common import Client

    app, store = create_app(tmp_path / "auth-boundary.sqlite3")
    event_id = store.create_event("Awards")
    client = Client(app)

    assert client.get("/").status_code == 303
    setup_page = client.get("/login").text
    assert "Admin setup required" in setup_page
    assert "uv run fastprize-admin create you@example.com" in setup_page
    assert client.get(f"/events/{event_id}").status_code == 303
    assert client.get(f"/events/{event_id}/display-link").status_code == 303
    assert client.get(f"/events/{event_id}/display").status_code == 200
    assert client.get(f"/events/{event_id}/display/latest-fragment").status_code == 200
    assert client.get(f"/events/{event_id}/display/latest").status_code == 200
    assert client.get("/assets/theme.js").status_code == 200


@pytest.mark.parametrize("has_admin", [False, True])
def test_login_page_uses_focused_layout_without_management_links(tmp_path, has_admin):
    app, store = create_app(tmp_path / "login-layout.sqlite3")
    if has_admin:
        store.create_admin("operator@example.test", hash_password("test-password-123"))

    page = Client(app).get("/login").text

    assert 'href="/events"' not in page
    assert 'href="/admin/accounts"' not in page
    assert 'class="left drawer' not in page
    assert "<footer" not in page
    assert 'alt="FastPrize logo"' in page
    assert 'data-theme-mode="toggle"' not in page
    assert 'data-theme-picker-open="true"' not in page
    assert 'id="theme-color-picker"' not in page
    body_tag = re.search(r"<body\b[^>]*>", page)
    assert body_tag is not None
    assert 'class="dark"' in body_tag.group()
    assert 'data-theme-fixed="dark"' in body_tag.group()
    assert 'class="s12 m8 l4"' in page
    assert 'class="grid"' in page
    assert 'class="grid large-space"' not in page
    assert page.count("<main") == 1
    if has_admin:
        assert 'action="/login"' in page
        assert 'autocomplete="username"' in page
        assert 'autocomplete="current-password"' in page
        assert 'name="csrf"' in page
        assert page.index('id="email"') < page.index('for="email"')
        assert page.index('id="password"') < page.index('for="password"')


def test_accounts_page_preserves_selected_event_navigation_and_styles_forms(tmp_path):
    app, store = create_app(tmp_path / "accounts-layout.sqlite3")
    event_id = store.create_event("Awards")
    client = _test_client(app)
    client.get(f"/events/{event_id}")
    workspace = client.get(f"/events/{event_id}/history").text
    accounts = client.get("/admin/accounts").text

    for page in (workspace, accounts):
        for section in ("entrants", "prizes", "draw", "history"):
            assert f'href="/events/{event_id}/{section}"' in page
        assert f'hx-get="/events/{event_id}/display-link"' in page
        assert 'href="/admin/accounts"' in page
        assert 'id="display-link-modal"' in page
    assert 'aria-current="page"' in accounts
    assert 'id="admin-counts"' in accounts
    assert "1 total | 1 enabled" in accounts
    assert 'id="admin-add-expansion"' in accounts
    assert 'data-add-expansion="true"' in accounts
    assert (
        'class="card padding secondary-container small-round vertical bottom-padding"'
        in accounts
    )
    assert (
        'class="s12 m6 l6 card padding tertiary-container small-round vertical"'
        in accounts
    )
    assert (
        'class="grid small-space" id="admin-list"' in accounts
        or 'id="admin-list" class="grid small-space"' in accounts
    )
    assert accounts.count('class="s6 m6 l6 field label border fill round extra"') == 2
    assert accounts.index('id="new-email"') < accounts.index('for="new-email"')
    created = client.post(
        "/admin/accounts",
        data={"email": "second@example.test", "password": "second-admin-password"},
    ).text
    assert "Admin account created." in created
    assert f'href="/events/{event_id}/draw"' in created
    assert store.get_admin_by_email("second@example.test") is not None


def test_admin_disable_requires_confirmation_dialog_and_keeps_final_admin_guard(
    tmp_path,
):
    app, store = create_app(tmp_path / "admin-disable-dialog.sqlite3")
    client = _test_client(app)
    current = store.get_admin_by_email("test-admin@example.test")
    assert current is not None
    target = store.create_admin(
        "target@example.test", hash_password("target-password-123")
    )
    disabled = store.create_admin(
        "disabled@example.test", hash_password("disabled-password-123")
    )
    store.set_admin_enabled(disabled["id"], False)
    page = client.get("/admin/accounts").text
    dialog_id = f"disable-admin-dialog-{target['id']}"
    dialog = re.search(
        rf'<dialog\b[^>]*id="{dialog_id}"[^>]*>.*?</dialog>', page, re.DOTALL
    )
    assert dialog is not None
    assert f'aria-controls="{dialog_id}"' in page
    assert f'data-ui="#{dialog_id}"' in page
    assert "Disable admin?" in dialog.group()
    assert "target@example.test" in dialog.group()
    assert "existing sessions will end" in dialog.group()
    assert ">Cancel</button>" in dialog.group()
    assert 'name="csrf"' in dialog.group()
    assert 'name="enabled" value="0"' in dialog.group()
    assert f'action="/admin/accounts/{target["id"]}/enabled"' in dialog.group()
    assert f'action="/admin/accounts/{target["id"]}/delete"' in dialog.group()
    assert ">Delete</span>" in dialog.group()
    assert "This cannot be undone." in dialog.group()
    assert f'id="disable-admin-dialog-{disabled["id"]}"' not in page
    assert store.get_admin(target["id"])["enabled"] == 1

    response = client.post(
        f"/admin/accounts/{target['id']}/enabled", data={"enabled": "0"}
    )
    assert "Admin account updated." in response.text
    assert store.get_admin(target["id"])["enabled"] == 0
    rejected = client.post(
        f"/admin/accounts/{current['id']}/enabled", data={"enabled": "0"}
    )
    assert "The final enabled admin cannot be disabled." in rejected.text
    assert store.get_admin(current["id"])["enabled"] == 1


def test_admin_delete_revokes_sessions_and_rejects_unsafe_requests(tmp_path):
    app, store = create_app(tmp_path / "admin-delete.sqlite3")
    client = _test_client(app)
    target = store.create_admin(
        "target@example.test", hash_password("target-password-123")
    )
    target_client = Client(app)
    target_client.cli.headers.update({"Origin": "http://testserver"})
    page = target_client.get("/login").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', page)
    assert csrf is not None
    target_client.post(
        "/login",
        data={
            "email": target["email"],
            "password": "target-password-123",
            "csrf": csrf.group(1),
        },
    )
    assert target_client.get("/admin/accounts").status_code == 200
    delete_url = f"/admin/accounts/{target['id']}/delete"
    assert (
        Client(app)
        .post(delete_url, headers={"Origin": "http://testserver"})
        .status_code
        == 303
    )
    assert (
        client.post(
            delete_url, headers={"Origin": "https://untrusted.example"}
        ).status_code
        == 403
    )
    assert store.get_admin(target["id"]) is not None
    assert client.get(delete_url).status_code == 405
    deleted = client.post(delete_url)
    assert "Admin account deleted." in deleted.text
    assert store.get_admin(target["id"]) is None
    replacement = store.create_admin(
        "replacement@example.test", hash_password("replacement-password-123")
    )
    assert replacement["id"] == target["id"]
    assert target_client.get("/admin/accounts").status_code == 303
    store.set_admin_enabled(replacement["id"], False)
    current = store.get_admin_by_email("test-admin@example.test")
    assert current is not None
    rejected = client.post(f"/admin/accounts/{current['id']}/delete")
    assert "The final enabled admin cannot be deleted." in rejected.text
    assert store.get_admin(current["id"]) is not None
    store.set_admin_enabled(replacement["id"], True)
    self_deleted = client.post(f"/admin/accounts/{current['id']}/delete")
    assert "Admin sign in" in self_deleted.text
    assert store.get_admin(current["id"]) is None
    assert store.get_admin(replacement["id"])["enabled"] == 1


def test_admin_login_logout_and_account_disable_revoke_session(tmp_path):
    from fasthtml.common import Client

    app, store = create_app(tmp_path / "auth-session.sqlite3")
    first = store.create_admin(
        "first@example.test", hash_password("first-admin-password")
    )
    second_hash = hash_password("second-admin-password")
    second = store.create_admin("second@example.test", second_hash)
    client = Client(app)
    client.cli.headers.update({"Origin": "http://testserver"})

    login_page = client.get("/login").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', login_page)
    assert csrf is not None
    rejected = client.post(
        "/login",
        data={
            "email": "first@example.test",
            "password": "wrong-password",
            "csrf": csrf.group(1),
        },
    )
    assert "Sign-in failed. Check your email and password." in rejected.text

    login_page = client.get("/login").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', login_page)
    assert csrf is not None
    logged_in = client.post(
        "/login",
        data={
            "email": "first@example.test",
            "password": "first-admin-password",
            "csrf": csrf.group(1),
        },
    )
    assert logged_in.status_code == 303
    assert client.get("/").status_code == 200
    assert client.get("/admin/accounts").status_code == 200

    store.update_admin_password(
        first["id"], hash_password("reset-first-admin-password")
    )
    assert client.get("/").status_code == 303

    second_client = Client(app)
    second_client.cli.headers.update({"Origin": "http://testserver"})
    login_page = second_client.get("/login").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', login_page)
    assert csrf is not None
    second_client.post(
        "/login",
        data={
            "email": "second@example.test",
            "password": "second-admin-password",
            "csrf": csrf.group(1),
        },
    )
    assert second_client.get("/admin/accounts").status_code == 200
    logout_csrf = re.search(
        r'action="/logout".*?name="csrf" value="([^"]+)"',
        second_client.get("/admin/accounts").text,
        re.DOTALL,
    )
    assert logout_csrf is not None
    logout = second_client.post(
        "/logout",
        data={"csrf": logout_csrf.group(1)},
    )
    assert logout.status_code == 303
    assert second_client.get("/").status_code == 303

    second_login = second_client.get("/login").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', second_login)
    assert csrf is not None
    second_client.post(
        "/login",
        data={
            "email": "second@example.test",
            "password": "second-admin-password",
            "csrf": csrf.group(1),
        },
    )
    assert store.set_admin_enabled(second["id"], False)
    assert second_client.get("/").status_code == 303


def test_signed_in_session_cookie_lasts_seven_days(tmp_path):
    app, store = create_app(tmp_path / "session-lifetime.sqlite3")
    store.create_admin("operator@example.test", hash_password("test-password-123"))
    client = Client(app)
    client.cli.headers.update({"Origin": "http://testserver"})
    page = client.get("/login").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', page)
    assert csrf is not None
    response = client.post(
        "/login",
        data={
            "email": "operator@example.test",
            "password": "test-password-123",
            "csrf": csrf.group(1),
        },
    )
    cookies = SimpleCookie()
    cookies.load(response.headers["set-cookie"])
    session_cookie = cookies["fastprize_session"]

    assert response.status_code == 303
    assert session_cookie["max-age"] == str(60 * 60 * 24 * 7)
    assert session_cookie["httponly"]
    assert session_cookie["samesite"].casefold() == "lax"


def test_secure_cookie_mode_requires_explicit_signing_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("FASTPRIZE_COOKIE_SECURE", "true")
    monkeypatch.delenv("FASTPRIZE_SESSION_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="FASTPRIZE_SESSION_SECRET"):
        create_app(tmp_path / "secure-cookie.sqlite3")


def test_admin_account_management_forms_create_reset_and_disable(tmp_path):
    app, store = create_app(tmp_path / "admin-management.sqlite3")
    client = _test_client(app)
    page = client.get("/admin/accounts").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', page)
    assert csrf is not None

    created = client.post(
        "/admin/accounts",
        data={
            "email": "second@example.test",
            "password": "second-admin-password",
            "csrf": csrf.group(1),
        },
    )
    second = store.get_admin_by_email("second@example.test")
    assert second is not None, created.text
    assert "Admin account created." in created.text

    reset = client.post(
        f"/admin/accounts/{second['id']}/password",
        data={"password": "updated-admin-password", "csrf": csrf.group(1)},
    )
    updated = store.get_admin(second["id"])
    assert "Password reset." in reset.text
    assert verify_password(updated["password_hash"], "updated-admin-password")

    disabled = client.post(
        f"/admin/accounts/{second['id']}/enabled",
        data={"enabled": "0", "csrf": csrf.group(1)},
    )
    assert "Admin account updated." in disabled.text
    assert store.get_admin(second["id"])["enabled"] == 0

    only_admin = store.get_admin_by_email("test-admin@example.test")
    rejected = client.post(
        f"/admin/accounts/{only_admin['id']}/enabled",
        data={"enabled": "0", "csrf": csrf.group(1)},
    )
    assert "The final enabled admin cannot be disabled." in rejected.text


def test_environment_bootstrap_creates_only_first_admin(tmp_path, monkeypatch):
    database = tmp_path / "bootstrap-admin.sqlite3"
    monkeypatch.setenv("FASTPRIZE_ADMIN_EMAIL", "First@Example.test")
    monkeypatch.setenv("FASTPRIZE_ADMIN_PASSWORD", "bootstrap-password-123")

    _, store = create_app(database)
    first_admin = store.get_admin_by_email("first@example.test")
    assert first_admin is not None
    assert first_admin["password_hash"] != "bootstrap-password-123"

    monkeypatch.setenv("FASTPRIZE_ADMIN_EMAIL", "Changed@Example.test")
    monkeypatch.setenv("FASTPRIZE_ADMIN_PASSWORD", "changed-password-123")
    _, restarted_store = create_app(database)
    assert restarted_store.admin_count() == 1
    assert restarted_store.get_admin_by_email("first@example.test") is not None
    assert restarted_store.get_admin_by_email("changed@example.test") is None


def test_login_rejects_cross_origin_posts_and_throttles_bad_passwords(tmp_path):
    from fasthtml.common import Client

    app, store = create_app(tmp_path / "login-security.sqlite3")
    store.create_admin("operator@example.test", hash_password("valid-password-123"))
    client = Client(app)
    login_page = client.get("/login").text
    csrf = re.search(r'name="csrf" value="([^"]+)"', login_page)
    assert csrf is not None

    cross_origin = client.post(
        "/login",
        headers={"Origin": "https://attacker.example"},
        data={
            "email": "operator@example.test",
            "password": "wrong-password",
            "csrf": csrf.group(1),
        },
    )
    assert cross_origin.status_code == 403

    client.cli.headers.update({"Origin": "http://testserver"})
    for _ in range(5):
        client.post(
            "/login",
            data={
                "email": "operator@example.test",
                "password": "wrong-password",
                "csrf": csrf.group(1),
            },
        )
    blocked = client.post(
        "/login",
        data={
            "email": "operator@example.test",
            "password": "valid-password-123",
            "csrf": csrf.group(1),
        },
    )
    assert "Sign-in failed. Check your email and password." in blocked.text
    assert store.admin_login_is_limited("operator@example.test", time.time())


def test_live_display_replaces_expired_winner_with_stable_quote():
    assert TECHNOLOGY_QUOTES
    assert all(not re.match(r"^\d+\.\s", quote) for quote in TECHNOLOGY_QUOTES)
    now = datetime.now(UTC)
    draw = {
        "id": 42,
        "entrant_name": "Ada Lovelace",
        "created_at": (now - timedelta(minutes=3, seconds=10)).isoformat(),
    }

    first_fragment = winner_fragment(draw, poll_url="/latest")
    second_fragment = winner_fragment(draw, poll_url="/latest")
    next_interval_draw = {
        **draw,
        "created_at": (now - timedelta(minutes=6, seconds=10)).isoformat(),
    }
    next_interval_fragment = winner_fragment(next_interval_draw, poll_url="/latest")

    first_html = to_xml(first_fragment)
    second_html = to_xml(second_fragment)
    next_interval_html = to_xml(next_interval_fragment)
    selected_quote = next(quote for quote in TECHNOLOGY_QUOTES if quote in first_html)
    assert (
        f'<h1 class="center-align live-display-quote italic">"{selected_quote}"</h1>'
        in first_html
    )
    assert first_html == second_html
    assert first_html != next_interval_html
    assert 'data-display-state="quote"' in first_html
    assert 'id="live-result"' in first_html
    assert 'hx-get="/latest"' in first_html
    assert 'class="center-align live-display-quote italic"' in first_html
    assert "Ada Lovelace" not in first_html


def test_event_workflow_and_live_display(tmp_path):
    app, store = create_app(tmp_path / "web.sqlite3")
    client = _test_client(app)

    home = client.get("/")
    assert home.status_code == 200
    assert "FastPrize" in home.text
    assert "Draw Center" in home.text
    assert 'href="/assets/fastprize-favicon.svg"' in home.text
    assert "/assets/fastprize-logo.svg" in home.text
    assert re.search(r'src="/assets/theme\.js\?v=\d+"', home.text)
    assert re.search(r'src="/assets/interactions\.js\?v=\d+"', home.text)
    assert client.get("/assets/fastprize-logo.svg").status_code == 200
    assert client.get("/assets/fastprize-favicon.svg").status_code == 200
    assert (
        "left drawer large-padding max m l small-width surface-container" in home.text
    )
    assert 'class="bottom-margin"' in home.text
    assert 'class="tiny-margin bottom-margin"' in home.text
    assert (
        "Hats are for pulling rabbits, not folded slips. We do it pseudo-randomly."
        in home.text
    )
    assert "Your events" not in home.text
    assert "DRAW OPERATIONS" not in home.text
    assert 'href="/events"' in home.text
    assert "Create event" in home.text
    assert (
        'href="/events" class="button primary responsive extra bottom-margin"'
        in home.text
    )
    assert "beercss@5.0.3/dist/cdn/beer.min.css" in home.text
    assert "beercss@5.0.3/dist/cdn/beer.min.js" in home.text
    assert "htmx.org@" in home.text
    assert (
        "material-dynamic-colors@1.1.4/dist/cdn/material-dynamic-colors.min.js"
        in home.text
    )
    assert home.text.count('data-theme-mode="toggle"') == 2
    assert 'id="theme-controls-desktop"' in home.text
    assert 'id="theme-controls-mobile"' in home.text
    assert 'id="theme-color-picker"' in home.text
    assert home.text.count('data-theme-picker-open="true"') == 2
    assert home.text.count("<i>palette</i>") == 2
    assert 'class="circle transparent"' in home.text
    assert 'aria-haspopup="dialog"' in home.text
    assert 'id="theme-color-picker"' in home.text
    assert 'aria-label="Choose theme color"' in home.text
    assert 'method="dialog"' in home.text
    palettes = (
        ("sapphire", "#82B1FF", "#3159A6"),
        ("jade", "#6DD6B0", "#087F5B"),
        ("coral", "#F28B82", "#B3261E"),
        ("marigold", "#FFD166", "#8C5A00"),
    )
    assert home.text.count('data-theme-palette="') == 4
    for name, dark_color, light_color in palettes:
        assert f'data-theme-palette="{name}"' in home.text
        assert f'data-theme-color-dark="{dark_color}"' in home.text
        assert f'data-theme-color-light="{light_color}"' in home.text
    assert 'href="/assets/theme-palette.css?v=3"' in home.text
    palette_styles = client.get("/assets/theme-palette.css").text
    assert palette_styles.count("button.circle[data-theme-palette=") == 4
    for name, dark_color, light_color in palettes:
        assert f'button.circle[data-theme-palette="{name}"]' in palette_styles
        assert (
            f"linear-gradient(135deg, {light_color} 50%, {dark_color} 50%)"
            in palette_styles
        )
    assert '<body class="light"' in home.text
    assert "<style" not in home.text.lower()
    assert "class-=" not in home.text

    events_page = client.get("/events")
    assert events_page.status_code == 200
    assert "<hr" not in events_page.text
    assert events_page.text.count("card padding primary-container small-round") == 1
    assert events_page.text.count("card padding secondary-container small-round") == 2
    assert "card padding tertiary-container small-round" not in events_page.text
    assert events_page.text.index("Choose your event.") < events_page.text.index(
        "Create an event"
    )
    assert events_page.text.index("Create an event") < events_page.text.index(
        "Your events"
    )
    assert "EVENTS" not in events_page.text
    assert 'class="grid bottom-padding"' in events_page.text
    assert 'class="primary-text"' in events_page.text
    assert "Create event" in events_page.text
    assert 'class="s12 m7 field label border fill round extra"' in events_page.text
    assert '<label for="event-name">Event name</label>' in events_page.text
    assert 'class="s12 m5 responsive extra primary"' in events_page.text
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
    assert "<div>Live Display</div>" in workspace.text
    assert "Public display" not in workspace.text
    assert "Open projector display" not in workspace.text
    assert 'class="active tiny-margin bottom-margin"' in workspace.text
    assert (
        'class="card padding primary-container small-round vertical bottom-padding"'
        in workspace.text
    )
    assert (
        workspace.text.count("card padding secondary-container small-round vertical")
        == 5
    )
    assert (
        workspace.text.count('class="s6 card padding tertiary-container small-round"')
        == 4
    )
    assert (
        '<section class="s12 m6 card padding secondary-container small-round vertical bottom-padding">'
        in workspace.text
    )
    assert '<h2 class="small">Entrants</h2>' in workspace.text
    assert '<h2 class="small">Prizes</h2>' in workspace.text
    assert workspace.text.count('<h3 class="extra">0</h3>') == 4
    assert 'class="grid small-space"' in workspace.text
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
    assert "<i>delete</i><span>Clear Database</span>" in workspace.text
    assert "<i>delete_forever</i><span>Delete event</span>" in workspace.text
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
        if section != "import":
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
    assert 'for="entrants-file"' in import_page.text
    assert 'for="prizes-file"' in import_page.text
    assert 'data-filename-target="entrants-file-name"' in import_page.text
    assert 'data-filename-target="prizes-file-name"' in import_page.text
    assert import_page.text.count("attach_file") == 2
    assert (
        '<button type="submit" class="s12 responsive extra primary">'
        in import_page.text
    )

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
    assert '<body class="screen"' in initial_display.text
    assert "The next name could be yours." in initial_display.text

    preview_page = client.post(f"/events/{event_id}/draws/{prize_id}/preview")
    assert preview_page.status_code == 200
    preview_winner_id = store.latest_preview(event_id)["entrant_id"]
    preview = client.get(
        f"/events/{event_id}/draw?preview={prize_id}&winner={preview_winner_id}"
    )
    assert store.latest_preview(event_id)["entrant_name"] in preview.text
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
    assert "The draw is complete. The projector is updating now." not in award_page.text
    assert re.search(
        r'<button\b[^>]*\bdisabled(?:="")?[^>]*>Awarded</button>', award_page.text
    )
    assert (
        f'action="/events/{event_id}/draws/{prize_id}/preview"' not in award_page.text
    )
    ordered_prizes = store.prizes(event_id)
    prize_positions = [
        award_page.text.index(f"<strong>{prize['prize_name']}</strong>")
        for prize in ordered_prizes
    ]
    assert prize_positions == sorted(prize_positions)
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
        data={"name": "Laptop", "sponsor": "Northwind", "number": "0007"},
    )
    prize_id = store.prizes(event_id)[0]["id"]
    assert store.prizes(event_id)[0]["number"] == "0007"
    edited_prize = client.post(
        f"/events/{event_id}/prizes/{prize_id}/edit",
        data={"name": "Tablet", "sponsor": "Contoso", "number": "0012"},
    )
    assert "Tablet" in edited_prize.text
    assert store.prizes(event_id)[0]["sponsor"] == "Contoso"
    assert store.prizes(event_id)[0]["number"] == "0012"
    client.post(f"/events/{event_id}/prizes/{prize_id}/remove")
    assert store.prizes(event_id) == []


def test_prize_mutations_return_htmx_fragments(tmp_path):
    app, store = create_app(tmp_path / "prize-htmx.sqlite3")
    event_id = store.create_event("Awards")
    prize_id = store.add_prize(event_id, "Laptop", "Northwind", "0007")
    client = _test_client(app)
    headers = {"HX-Request": "true"}

    page = client.get(f"/events/{event_id}/prizes").text
    assert 'id="prize-add-expansion"' in page
    assert 'data-add-expansion="true"' in page
    assert 'aria-expanded="false"' in page
    assert "data-add-expansion-chevron" in page
    assert ">expand_more</i>" in page
    assert 'id="prize-number"' in page
    assert 'class="grid middle-align small-space top-margin bottom-margin"' in page
    assert 'class="s6"># 0007</small>' in page
    assert f'data-hide-while-editing="prize-info-{prize_id}"' in page
    assert page.index('class="s6"># 0007</small>') < page.index(
        f'hx-get="/events/{event_id}/prizes/{prize_id}/edit"'
    )
    assert "style=" not in page
    assert 'id="prize-counts"' in page
    assert (
        'class="s12 m12 l6 card padding tertiary-container small-round vertical"'
        in page
    )
    assert f'id="prize-row-{prize_id}"' in page
    assert f'data-edit-target="prize-info-{prize_id}"' in page
    assert page.count(f'data-hide-while-editing="prize-info-{prize_id}"') == 3
    assert f'hx-get="/events/{event_id}/prizes/{prize_id}/edit"' in page
    assert f'hx-post="/events/{event_id}/prizes/{prize_id}/remove"' in page
    prize_dialog = f"remove-prize-dialog-{prize_id}"
    assert f'id="{prize_dialog}"' in page
    assert 'class="modal padding medium-width left-align"' in page
    assert 'aria-label="Confirm removing Laptop"' in page
    assert f'aria-controls="{prize_dialog}"' in page
    assert page.count(f'data-ui="#{prize_dialog}"') == 2
    assert f'action="/events/{event_id}/prizes/{prize_id}/remove"' in page
    assert f'action="/events/{event_id}/draws/{prize_id}"' not in page
    assert "<i>casino</i><span>Draw</span>" not in page
    assert f'href="/events/{event_id}/draw"' in page

    edit_form = client.get(f"/events/{event_id}/prizes/{prize_id}/edit").text
    assert "style=" not in edit_form
    assert 'name="name" value="Laptop"' in edit_form
    assert 'name="sponsor" value="Northwind"' in edit_form
    assert 'name="number" value="0007"' in edit_form
    assert "data-inline-edit" in edit_form
    assert edit_form.count('class="field round fill border"') == 3
    assert 'class="circle primary"' in edit_form
    assert 'class="circle"' in edit_form
    assert 'aria-label="Save prize"' in edit_form
    assert 'aria-label="Cancel edit"' in edit_form
    assert f'hx-post="/events/{event_id}/prizes/{prize_id}/edit"' in edit_form

    edited = client.post(
        f"/events/{event_id}/prizes/{prize_id}/edit",
        data={"name": "Tablet", "sponsor": "Contoso", "number": "0009"},
        headers=headers,
    )
    assert "<!doctype html>" not in edited.text
    assert f'id="prize-row-{prize_id}"' in edited.text
    assert "Tablet" in edited.text
    assert 'class="s6"># 0009</small>' in edited.text
    assert store.prizes(event_id)[0]["number"] == "0009"
    assert "Prize updated." not in edited.text

    removed = client.post(
        f"/events/{event_id}/prizes/{prize_id}/remove",
        headers=headers,
    )
    assert "<!doctype html>" not in removed.text
    assert 'hx-swap-oob="outerHTML"' in removed.text
    assert "0 available | 0 total" in removed.text
    assert "Prize removed." not in removed.text
    assert store.prizes(event_id) == []


def test_prize_search_filters_names_and_sponsors(tmp_path):
    app, store = create_app(tmp_path / "prize-search.sqlite3")
    event_id = store.create_event("Awards")
    store.add_prize(event_id, "Laptop", "Northwind")
    store.add_prize(event_id, "Coffee basket", "Contoso", "0042")
    client = _test_client(app)

    page = client.get(f"/events/{event_id}/prizes").text
    assert 'id="prize-search"' in page
    assert 'class="s12 m6 field large prefix round fill border active"' in page
    assert f'hx-get="/events/{event_id}/prizes/search"' in page
    assert 'hx-target="#prize-list"' in page

    by_name = client.get(f"/events/{event_id}/prizes/search?search=COFFEE").text
    assert "Coffee basket" in by_name
    assert "Laptop" not in by_name

    by_sponsor = client.get(f"/events/{event_id}/prizes/search?search=northwind").text
    assert "Laptop" in by_sponsor
    assert "Coffee basket" not in by_sponsor

    by_number = client.get(f"/events/{event_id}/prizes/search?search=0042").text
    assert "Coffee basket" in by_number
    assert "# 0042" in by_number
    assert "Laptop" not in by_number

    no_matches = client.get(f"/events/{event_id}/prizes/search?search=missing").text
    assert "No prizes match your search." in no_matches
    assert (
        '<p class="s12 secondary-text">No prizes match your search.</p>' in no_matches
    )


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
    assert 'method="post"' in clear_form
    assert "Cleared all entrants and prizes." not in reset_page.text
    assert store.entrants(event_id) == []
    assert store.prizes(event_id) == []


def test_operator_can_delete_event_and_returns_to_events(tmp_path):
    app, store = create_app(tmp_path / "delete-event.sqlite3")
    client = _test_client(app)
    client.cli.follow_redirects = False
    event_id = store.create_event("Awards")
    store.add_entrant(event_id, "Ada Lovelace")
    store.add_prize(event_id, "Laptop")

    response = client.post(f"/events/{event_id}/delete")

    assert response.status_code == 303
    assert response.headers["location"] == "/events"
    assert store.get_event(event_id) is None
    assert store.entrants(event_id) == []
    assert store.prizes(event_id) == []
