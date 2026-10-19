import json
from urllib.parse import quote

from fasthtml.common import (
    H1,
    H2,
    A,
    Body,
    Details,
    Dialog,
    Div,
    Form,
    Head,
    Html,
    Input,
    Link,
    Main,
    Meta,
    Nav,
    Option,
    Optgroup,
    P,
    RedirectResponse,
    Script,
    Select,
    Span,
    Strong,
    Summary,
    Title,
    Ul,
)
from fasthtml.components import Uk_theme_switcher
from monsterui.franken import Button as ThemeButton
from monsterui.franken import ButtonT, UkIcon

EVENT_SELECTION_COOKIE = "fastprize_event_id"

THEMES = (
    ("uk-theme-slate", "Slate", "#64748b", True),
    ("uk-theme-blue", "Blue", "#2563eb", False),
    ("uk-theme-green", "Green", "#16a34a", False),
    ("uk-theme-rose", "Rose", "#e11d48", False),
    ("uk-theme-yellow", "Yellow", "#facc15", False),
)

NAV_ITEMS = (
    ("draw", "Draw", "dices", "show"),
    ("display", "Live display", "monitor", "show"),
    ("history", "History", "history", "show"),
    ("entrants", "Entrants", "users", "setup"),
    ("prizes", "Prizes", "gift", "setup"),
    ("overview", "Manage", "settings", "setup"),
    ("events", "Events", "calendar", None),
)

MOBILE_KEYS = ("draw", "display", "entrants", "prizes", "overview")

THEME_SCRIPT = """
const htmlElement = document.documentElement;
const __FRANKEN__ = JSON.parse(localStorage.getItem("__FRANKEN__") || "{}");
if (
    __FRANKEN__.mode === "dark" ||
    (!__FRANKEN__.mode &&
        window.matchMedia("(prefers-color-scheme: dark)").matches)
) {
    htmlElement.classList.add("dark");
} else {
    htmlElement.classList.remove("dark");
}
htmlElement.classList.add(__FRANKEN__.theme || "uk-theme-slate");
htmlElement.classList.add(__FRANKEN__.radii || "uk-radii-sm");
htmlElement.classList.add(__FRANKEN__.shadows || "uk-shadows-sm");
htmlElement.classList.add(__FRANKEN__.font || "uk-font-sm");
"""

STATUS_MESSAGES = {
    "event-created": "Event created.",
    "entrant-added": "Entrant added.",
    "entrant-updated": "Entrant updated.",
    "entrant-removed": "Entrant removed.",
    "prize-added": "Prize added.",
    "prize-updated": "Prize updated.",
    "prize-removed": "Prize removed.",
    "data-cleared": "Cleared all entrants and prizes.",
    "settings-updated": "Winner eligibility setting updated.",
    "entrants-imported": "Entrant CSV imported.",
    "prizes-imported": "Prize CSV imported.",
    "draw-complete": "The draw is complete. The projector is updating now.",
    "no-eligible-entrants": "Add an eligible entrant before drawing this prize.",
    "no-file": "Choose a CSV file to import.",
    "invalid-entrant": "Entrant name is required, and duplicate names are skipped.",
    "invalid-prize": "Prize name is required.",
    "invalid-prize-number": "Prize number must be a whole number.",
    "prize-locked": "Awarded prizes cannot be changed or removed.",
    "invalid-encoding": "The CSV file must use UTF-8 text encoding.",
    "event-missing": "That event could not be found.",
}


def redirect_event(event_id: int, status: str, page: str = "events"):
    suffix = "" if page == "events" else f"/{page}"
    return RedirectResponse(
        f"/events/{event_id}{suffix}?status={quote(status, safe='')}",
        status_code=303,
    )


def status_message(status: str) -> str:
    if status.startswith("imports-completed:"):
        reports = json.loads(status.removeprefix("imports-completed:"))
        imported = []
        if "entrants" in reports:
            added = reports["entrants"]["added"]
            imported.append(f"{added} entrant{'s' if added != 1 else ''}")
        if "prizes" in reports:
            added = reports["prizes"]["added"]
            imported.append(f"{added} prize{'s' if added != 1 else ''}")
        message = f"Imported {' and '.join(imported)}"
        if "entrants" in reports:
            duplicates = reports["entrants"]["duplicates"]
            message += (
                f"; {duplicates} duplicate entrant row"
                f"{'s' if duplicates != 1 else ''} skipped"
            )
        errors = [error for report in reports.values() for error in report["errors"]]
        message += f"; {len(errors)} invalid row{'s' if len(errors) != 1 else ''}."
        if errors:
            message += " " + "; ".join(errors)
        return message
    if status.startswith(("entrants-imported:", "prizes-imported:")):
        kind, added, duplicates, error_count, *details = status.split(":", 4)
        label = "entrant" if kind == "entrants-imported" else "prize"
        message = (
            f"Imported {added} {label}{'' if added == '1' else 's'}; "
            f"{duplicates} duplicate row{'s' if duplicates != '1' else ''} skipped; "
            f"{error_count} invalid row{'s' if error_count != '1' else ''}."
        )
        if details and details[0]:
            message += " " + details[0]
        return message
    return STATUS_MESSAGES.get(status, "")


def theme_headers():
    return (
        Link(rel="stylesheet", href="/assets/vendor/franken.css"),
        Script(type="module", src="/assets/vendor/franken.js"),
        Script(src="/assets/vendor/tailwind.js"),
        Script("tailwind.config = { darkMode: 'selector' };"),
        Script(THEME_SCRIPT),
        Script(type="module", src="/assets/vendor/franken-icons.js"),
        Link(rel="stylesheet", href="/assets/app.css"),
        Script(
            """
document.addEventListener("click", (event) => {
    for (const menu of document.querySelectorAll(".theme-menu[open], .info-tip[open]")) {
        if (!menu.contains(event.target)) menu.open = false;
    }
});
function startEdit(button) {
    const record = button.closest(".record");
    record.querySelectorAll("[data-read]").forEach((el) => { el.hidden = true; });
    record.querySelectorAll("[data-write]").forEach((el) => { el.hidden = false; });
    const field = record.querySelector(".record-edit input");
    if (field) field.focus();
}
function cancelEdit(button) {
    const record = button.closest(".record");
    record.querySelectorAll("[data-write]").forEach((el) => { el.hidden = true; });
    record.querySelectorAll("[data-read]").forEach((el) => { el.hidden = false; });
}
function filterRecords(input) {
    const query = input.value.trim().toLowerCase();
    const list = document.getElementById(input.dataset.list);
    if (!list) return;
    list.querySelectorAll("[data-search]").forEach((row) => {
        row.hidden = query !== "" && !row.dataset.search.includes(query);
    });
}
function confirmDelete(button) {
    const dialog = document.getElementById("confirm-delete");
    document.getElementById("confirm-delete-message").textContent = button.dataset.confirm;
    const form = document.getElementById("confirm-delete-form");
    form.action = button.dataset.confirmAction;
    form.querySelector("button").textContent = button.dataset.confirmLabel || "Remove";
    if (!dialog.open) dialog.showModal();
}
"""
        ),
    )


def theme_picker():
    theme_options = [
        Option(label, value=value, data_hex=color, selected=selected or None)
        for value, label, color, selected in THEMES
    ]
    return Details(
        Summary(
            UkIcon("palette"),
            aria_label="Choose theme",
            cls="theme-trigger",
        ),
        Div(
            Uk_theme_switcher(
                Select(
                    Optgroup(*theme_options, data_key="theme", label="Theme"),
                    Optgroup(
                        Option("Light", value="light", data_icon="sun"),
                        Option("Dark", value="dark", data_icon="moon"),
                        data_key="mode",
                        label="Mode",
                    ),
                    hidden=True,
                ),
                id="theme-switcher",
            ),
            cls="theme-panel",
        ),
        cls="theme-menu",
    )


def _href(key: str, event_id: int | None) -> str:
    if key == "events" or event_id is None:
        return "/events"
    if key == "overview":
        return f"/events/{event_id}"
    return f"/events/{event_id}/{key}"


def _nav_link(key: str, label: str, icon: str, event_id: int | None, active_link: str):
    attributes = {}
    if key == "display":
        attributes["target"] = "_blank"
        attributes["rel"] = "noopener"
    return A(
        UkIcon(icon),
        Span(label),
        href=_href(key, event_id),
        cls="nav-link",
        aria_current="page" if active_link == key else None,
        **attributes,
    )


def _grouped_nav(event_id: int | None, active_link: str, keys: tuple[str, ...] | None):
    items = [
        item
        for item in NAV_ITEMS
        if (event_id is not None or item[0] == "events")
        and (keys is None or item[0] in keys)
    ]
    groups = []
    current_label = object()
    bucket = []
    for key, label, icon, group in items:
        if group != current_label and bucket:
            groups.append((current_label, bucket))
            bucket = []
        current_label = group
        bucket.append(_nav_link(key, label, icon, event_id, active_link))
    if bucket:
        groups.append((current_label, bucket))
    rendered = []
    for group, links in groups:
        label = {"show": "Show", "setup": "Setup"}.get(group, "")
        rendered.append(
            Div(
                P(label, cls="nav-label") if label else "",
                *links,
                cls="nav-group",
            )
        )
    return rendered


def document(
    title: str,
    *content,
    screen: bool = False,
    event_id: int | None = None,
    event_name: str | None = None,
    active_link: str = "",
):
    if screen:
        body = (
            Main(*content, cls="live-stage"),
            Div(theme_picker(), cls="theme-dock"),
        )
    else:
        brand = A(UkIcon("dices"), Span("FastPrize"), href="/", cls="brand")
        secondary_keys = tuple(
            key for key, *_rest in NAV_ITEMS if key not in MOBILE_KEYS
        )
        body = (
            Div(
                Nav(
                    brand,
                    P(event_name or "Choose an event", cls="nav-label"),
                    *_grouped_nav(event_id, active_link, None),
                    Div(theme_picker(), cls="sidebar-theme"),
                    cls="sidebar",
                ),
                Div(
                    Div(
                        brand,
                        DetailsMenu(event_id, active_link, secondary_keys)
                        if event_id is not None
                        else "",
                        cls="topbar",
                    ),
                    Main(*content, cls="main-pad"),
                ),
                Nav(
                    *(
                        _nav_link(key, label, icon, event_id, active_link)
                        for key, label, icon, _group in NAV_ITEMS
                        if (event_id is not None and key in MOBILE_KEYS)
                        or (event_id is None and key == "events")
                    ),
                    cls="mobile-bar",
                    aria_label="Primary",
                ),
                cls="app-shell",
            ),
            confirm_dialog(),
        )
    return Html(
        Head(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title(title),
            *theme_headers(),
        ),
        Body(*body, cls="bg-background text-foreground"),
    )


def DetailsMenu(event_id: int, active_link: str, keys: tuple[str, ...]):
    from fasthtml.common import Details, Summary

    return Details(
        Summary("More", cls="nav-link"),
        *_grouped_nav(event_id, active_link, keys),
        cls="more-menu mobile-only",
    )


def page_header(eyebrow: str, title: str, detail: str = ""):
    from monsterui.franken import H1

    return Div(
        P(eyebrow, cls="nav-label") if eyebrow else "",
        H1(title),
        P(detail) if detail else "",
        cls="page-header",
    )


def status_banner(message: str):
    if not message:
        return ""
    return P(message, cls="status-banner")


def record_list(records: list[dict], empty_message: str, render_record, list_id: str = ""):
    if not records:
        return P(empty_message, cls="empty-note")
    return Ul(
        *(render_record(record) for record in records),
        id=list_id or None,
        cls="uk-list uk-list-divider",
    )


def stat_card(value, label: str):
    from monsterui.franken import Card
    from monsterui.franken import H2 as CardHeading

    return Card(CardHeading(str(value)), P(label))


def search_field(list_id: str, label: str):
    from monsterui.franken import Input as Field

    return Div(
        Field(
            type="search",
            id=f"search-{list_id}",
            placeholder=label,
            aria_label=label,
            data_list=list_id,
            oninput="filterRecords(this)",
        ),
        UkIcon("search"),
        cls="search-field",
    )


def search_card(list_id: str, label: str):
    from monsterui.franken import Card

    return Card(search_field(list_id, label), body_cls="search-card")


def winner_fragment(draw: dict | None):
    if draw is None:
        return Div(
            P("The next name could be yours.", cls="live-idle"),
            id="live-result",
            cls="live-result",
            data_draw_id="",
            data_result_version="",
        )
    return Div(
        Div(
            H1(draw["entrant_name"], cls="live-name"),
            P("from", cls="live-join") if draw["organization"] else "",
            P(draw["organization"], cls="live-org") if draw["organization"] else "",
            cls="live-person",
        ),
        Div(
            P(draw["prize_name"], cls="live-prize"),
            P("sponsored by", cls="live-join"),
            P(draw["sponsor"] or "our conference sponsors", cls="live-sponsor"),
            cls="live-award",
        ),
        id="live-result",
        cls="live-result",
        data_draw_id=str(draw["id"]),
        data_result_version=draw["created_at"],
    )


def confirm_dialog():
    return Dialog(
        H2("Confirm removal"),
        P(id="confirm-delete-message"),
        Div(
            Form(
                ThemeButton("Remove", cls=ButtonT.destructive),
                id="confirm-delete-form",
                method="post",
            ),
            ThemeButton(
                "Cancel",
                type="button",
                onclick="this.closest('dialog').close()",
                cls=ButtonT.secondary,
            ),
            cls="cluster",
        ),
        id="confirm-delete",
        cls="draw-dialog",
    )


def draw_preview_modal(
    event_id: int, prize_id: int, winner_id: int, prize: dict, winner: dict
):
    return Div(
        Dialog(
            H2("Confirm draw"),
            P(
                f"{winner['name']} from {winner['organization'] or 'an unlisted organization'} has been selected for {prize['prize_name']}."
            ),
            Div(
                Form(
                    Input(type="hidden", name="winner", value=str(winner_id)),
                    ThemeButton("Award winner", cls=ButtonT.primary),
                    action=f"/events/{event_id}/draws/{prize_id}/award",
                    method="post",
                ),
                Form(
                    ThemeButton("Redraw", cls=ButtonT.secondary),
                    action=f"/events/{event_id}/draws/{prize_id}/preview",
                    method="post",
                ),
                cls="cluster",
            ),
            id="draw-confirmation",
            cls="draw-dialog",
        ),
        Script("document.getElementById('draw-confirmation').showModal()"),
        cls="contents",
    )
