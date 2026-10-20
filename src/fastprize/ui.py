import json
import random
from datetime import UTC, datetime, timedelta
from html import escape
from importlib.resources import files
from pathlib import Path
from urllib.parse import quote

from fasthtml.common import (
    H1,
    H2,
    A,
    Body,
    Button,
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
    NotStr,
    Optgroup,
    Option,
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
TECHNOLOGY_QUOTES = tuple(
    line.strip()
    for line in files("fastprize")
    .joinpath("quotes.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
)

THEMES = (
    ("uk-theme-slate", "Slate", "#64748b", True),
    ("uk-theme-stone", "Stone", "#78716c", False),
    ("uk-theme-gray", "Gray", "#6b7280", False),
    ("uk-theme-neutral", "Neutral", "#737373", False),
    ("uk-theme-zinc", "Zinc", "#71717a", False),
    ("uk-theme-red", "Red", "#dc2626", False),
    ("uk-theme-rose", "Rose", "#e11d48", False),
    ("uk-theme-orange", "Orange", "#f97316", False),
    ("uk-theme-green", "Green", "#16a34a", False),
    ("uk-theme-blue", "Blue", "#2563eb", False),
    ("uk-theme-yellow", "Yellow", "#facc15", False),
    ("uk-theme-violet", "Violet", "#7c3aed", False),
)
RADII = (
    ("uk-radii-none", "None", False),
    ("uk-radii-sm", "Small", True),
    ("uk-radii-md", "Medium", False),
    ("uk-radii-lg", "Large", False),
)
SHADOWS = (
    ("uk-shadows-none", "None", False),
    ("uk-shadows-sm", "Small", True),
    ("uk-shadows-md", "Medium", False),
    ("uk-shadows-lg", "Large", False),
)
FONTS = (
    ("uk-font-sm", "Small", True),
    ("uk-font-base", "Default", False),
)

NAV_ITEMS = (
    ("draw", "Draw", "dices", "show"),
    ("display", "Live display", "monitor", "show"),
    ("history", "History", "history", "show"),
    ("entrants", "Entrants", "users", "setup"),
    ("prizes", "Prizes", "gift", "setup"),
    ("overview", "Manage", "settings", "setup"),
    ("events", "Events", "calendar", None),
    ("accounts", "Admins", "shield", None),
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

WARNING_STATUSES = {
    "no-eligible-entrants",
    "no-file",
    "prize-locked",
    "award-missing",
}
ERROR_STATUSES = {
    "invalid-entrant",
    "invalid-prize",
    "invalid-prize-number",
    "invalid-encoding",
    "event-missing",
}

STATUS_MESSAGES = {
    "event-created": "Event created.",
    "entrant-added": "Entrant added.",
    "entrant-updated": "Entrant updated.",
    "entrant-removed": "Entrant removed.",
    "entrant-eligibility": "Entrant eligibility updated.",
    "prize-added": "Prize added.",
    "prize-updated": "Prize updated.",
    "prize-removed": "Prize removed.",
    "data-cleared": "Cleared all entrants and prizes.",
    "settings-updated": "Winner eligibility setting updated.",
    "entrants-imported": "Entrant CSV imported.",
    "prizes-imported": "Prize CSV imported.",
    "no-eligible-entrants": "Add an eligible entrant before drawing this prize.",
    "no-file": "Choose a CSV file to import.",
    "invalid-entrant": "Entrant name is required, and duplicate names are skipped.",
    "invalid-prize": "Prize name is required.",
    "invalid-prize-number": "Prize number must be a whole number.",
    "prize-locked": "Awarded prizes cannot be changed or removed.",
    "award-undone": "Award undone. The winner is eligible again.",
    "award-missing": "That award could not be undone.",
    "invalid-encoding": "The CSV file must use UTF-8 text encoding.",
    "event-missing": "That event could not be found.",
}


def award_status(name: str, organization: str = "") -> str:
    payload = json.dumps(
        {"name": name, "organization": organization or ""},
        separators=(",", ":"),
    )
    return f"draw-complete:{payload}"


def redirect_event(event_id: int, status: str, page: str = "events"):
    suffix = "" if page == "events" else f"/{page}"
    return RedirectResponse(
        f"/events/{event_id}{suffix}?status={quote(status, safe='')}",
        status_code=303,
    )


def status_tone(status: str) -> str:
    if status.startswith("imports-completed:"):
        reports = json.loads(status.removeprefix("imports-completed:"))
        added = sum(report["added"] for report in reports.values())
        duplicates = sum(report.get("duplicates", 0) for report in reports.values())
        errors = [error for report in reports.values() for error in report["errors"]]
        if errors and not added:
            return "error"
        if errors or duplicates:
            return "warning"
        return "info"
    if status.startswith(("entrants-imported:", "prizes-imported:")):
        _kind, added, duplicates, error_count, *_details = status.split(":", 4)
        if int(error_count) and int(added) == 0:
            return "error"
        if int(error_count) or int(duplicates):
            return "warning"
        return "info"
    if status in ERROR_STATUSES:
        return "error"
    if status in WARNING_STATUSES:
        return "warning"
    return "info"


def status_message(status: str) -> str:
    if status.startswith("draw-complete:"):
        awarded = json.loads(status.removeprefix("draw-complete:"))
        name = awarded["name"]
        organization = awarded.get("organization") or ""
        if organization:
            return f"Prize awarded to {name} of {organization}"
        return f"Prize awarded to {name}"
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
const scrollKey = "fastprize-scroll";
(function () {
    let saved = null;
    try {
        saved = JSON.parse(sessionStorage.getItem(scrollKey) || "null");
        sessionStorage.removeItem(scrollKey);
    } catch (error) {
        saved = null;
    }
    if (!saved || saved.path !== location.pathname) return;
    const y = Number(saved.y) || 0;
    if (!y) return;
    const restore = () => window.scrollTo(0, y);
    const observer = new MutationObserver(restore);
    observer.observe(document.documentElement, { childList: true, subtree: true });
    document.addEventListener("DOMContentLoaded", () => {
        restore();
        observer.disconnect();
    });
    window.addEventListener("load", () => {
        restore();
        requestAnimationFrame(restore);
    });
})();
document.addEventListener("submit", (event) => {
    if (!(event.target instanceof HTMLFormElement)) return;
    try {
        sessionStorage.setItem(scrollKey, JSON.stringify({
            path: location.pathname,
            y: window.scrollY,
        }));
    } catch (error) {}
});
document.addEventListener("click", (event) => {
    for (const menu of document.querySelectorAll(".theme-menu[open]")) {
        if (!menu.contains(event.target)) menu.open = false;
    }
    const dialog = event.target instanceof Element
        ? event.target.closest("dialog[open]")
        : null;
    if (!dialog) return;
    const bounds = dialog.getBoundingClientRect();
    const outside = event.clientX < bounds.left || event.clientX > bounds.right
        || event.clientY < bounds.top || event.clientY > bounds.bottom;
    if (outside) dialog.close();
});
function syncShadowLabel(switcher) {
    if (!switcher.keys || !switcher.keys.shadows) return;
    const label = document.documentElement.classList.contains("dark") ? "Glow" : "Shadow";
    if (switcher.keys.shadows.text === label) return;
    switcher.keys.shadows.text = label;
    switcher.requestUpdate();
}
function bindShadowLabel(switcher) {
    syncShadowLabel(switcher);
    switcher.addEventListener("uk-theme-switcher:change", () => syncShadowLabel(switcher));
}
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".toast").forEach((toast) => {
        window.setTimeout(() => toast.remove(), 10000);
    });
    document.querySelectorAll("[data-page-bar]").forEach((bar) => {
        const list = document.getElementById(bar.dataset.list);
        if (list) showRecordPage(list);
    });
    customElements.whenDefined("uk-theme-switcher").then(() => {
        document.querySelectorAll("uk-theme-switcher").forEach(bindShadowLabel);
    });
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
        const matches = query === "" || row.dataset.search.includes(query);
        row.dataset.pageMatch = matches ? "1" : "0";
    });
    list.dataset.page = "1";
    showRecordPage(list);
}
function showRecordPage(list) {
    const bar = document.querySelector('[data-page-bar="' + list.id + '"]');
    const pageSize = Number(bar?.dataset.pageSize || 20);
    const rows = [...list.querySelectorAll("[data-search]")];
    const matched = rows.filter((row) => row.dataset.pageMatch !== "0");
    const pages = Math.max(1, Math.ceil(matched.length / pageSize));
    let page = Number(list.dataset.page || 1);
    page = Math.min(Math.max(page, 1), pages);
    list.dataset.page = String(page);
    const start = (page - 1) * pageSize;
    matched.forEach((row, index) => {
        row.hidden = index < start || index >= start + pageSize;
    });
    rows.filter((row) => row.dataset.pageMatch === "0").forEach((row) => {
        row.hidden = true;
    });
    if (!bar) return;
    const label = bar.querySelector("[data-page-label]");
    if (label) label.textContent = "Page " + page + " of " + pages;
    bar.querySelectorAll("[data-page]").forEach((button) => {
        const action = button.dataset.page;
        const atStart = page <= 1;
        const atEnd = page >= pages;
        button.disabled = (action === "first" || action === "prev") ? atStart : atEnd;
    });
}
function changePage(button) {
    const list = document.getElementById(button.dataset.list);
    if (!list || button.disabled) return;
    const bar = document.querySelector('[data-page-bar="' + list.id + '"]');
    const pageSize = Number(bar?.dataset.pageSize || 20);
    const matched = [...list.querySelectorAll("[data-search]")].filter(
        (row) => row.dataset.pageMatch !== "0"
    );
    const pages = Math.max(1, Math.ceil(matched.length / pageSize));
    let page = Number(list.dataset.page || 1);
    if (button.dataset.page === "first") page = 1;
    else if (button.dataset.page === "prev") page -= 1;
    else if (button.dataset.page === "next") page += 1;
    else page = pages;
    list.dataset.page = String(page);
    showRecordPage(list);
}
function confirmDelete(button) {
    const dialog = document.getElementById("confirm-delete");
    document.getElementById("confirm-delete-message").innerHTML = button.dataset.confirm;
    const title = document.getElementById("confirm-delete-title");
    if (title) title.textContent = button.dataset.confirmTitle || "Confirm removal";
    const form = document.getElementById("confirm-delete-form");
    form.action = button.dataset.confirmAction;
    form.querySelector("button").textContent = button.dataset.confirmLabel || "Remove";
    const extra = form.querySelector("[data-extra]");
    if (extra) extra.remove();
    if (button.dataset.confirmField) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = button.dataset.confirmField;
        input.value = button.dataset.confirmValue || "";
        input.dataset.extra = "1";
        form.append(input);
    }
    if (!dialog.open) dialog.showModal();
}
function openDisplayLink() {
    const dialog = document.getElementById("display-link");
    const eventId = document.body.dataset.eventId;
    if (!dialog || !eventId) return;
    fetch("/events/" + eventId + "/display-link")
        .then((response) => response.ok ? response.text() : "")
        .then((html) => {
            if (!html) return;
            dialog.innerHTML = html;
            if (!dialog.open) dialog.showModal();
        });
}
"""
        ),
    )


def theme_picker():
    theme_options = [
        Option(label, value=value, data_hex=color, selected=selected or None)
        for value, label, color, selected in THEMES
    ]
    radius_options = [
        Option(label, value=value, selected=selected or None)
        for value, label, selected in RADII
    ]
    shadow_options = [
        Option(label, value=value, selected=selected or None)
        for value, label, selected in SHADOWS
    ]
    font_options = [
        Option(label, value=value, selected=selected or None)
        for value, label, selected in FONTS
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
                    Optgroup(*radius_options, data_key="radii", label="Radius"),
                    Optgroup(*shadow_options, data_key="shadows", label="Shadow"),
                    Optgroup(*font_options, data_key="font", label="Font"),
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
    if key == "accounts":
        return "/admin/accounts"
    if key == "events" or event_id is None:
        return "/events"
    if key == "overview":
        return f"/events/{event_id}"
    return f"/events/{event_id}/{key}"


def _nav_link(key: str, label: str, icon: str, event_id: int | None, active_link: str):
    if key == "display" and event_id is not None:
        return Button(
            UkIcon(icon),
            Span(label),
            type="button",
            cls="nav-link",
            onclick="openDisplayLink()",
        )
    return A(
        UkIcon(icon),
        Span(label),
        href=_href(key, event_id),
        cls="nav-link",
        aria_current="page" if active_link == key else None,
    )


def _grouped_nav(event_id: int | None, active_link: str, keys: tuple[str, ...] | None):
    items = [
        item
        for item in NAV_ITEMS
        if (event_id is not None or item[0] in {"events", "accounts"})
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


def brand_mark():
    svg = (
        Path(__file__).resolve().parents[2] / "assets" / "fastprize-favicon.svg"
    ).read_text(encoding="utf-8")
    return NotStr(svg)


def document(
    title: str,
    *content,
    screen: bool = False,
    login_page: bool = False,
    event_id: int | None = None,
    event_name: str | None = None,
    active_link: str = "",
):
    if screen:
        body = (
            Main(*content, cls="live-stage"),
            Div(theme_picker(), cls="theme-dock"),
        )
    elif login_page:
        body = (Main(*content, cls="login-shell"),)
    else:
        brand = A(brand_mark(), Span("FastPrize"), href="/", cls="brand")
        secondary_keys = tuple(
            key for key, *_rest in NAV_ITEMS if key not in MOBILE_KEYS
        )
        body = (
            Div(
                Nav(
                    brand,
                    P(event_name or "Choose an event", cls="nav-label"),
                    *_grouped_nav(event_id, active_link, None),
                    Div(
                        Div(theme_picker(), cls="sidebar-theme"),
                        Form(
                            ThemeButton("Sign out", type="submit", cls=ButtonT.ghost),
                            action="/logout",
                            method="post",
                        ),
                        cls="sidebar-footer",
                    ),
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
            Dialog(id="display-link", cls="draw-dialog") if event_id is not None else "",
        )
    return Html(
        Head(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title(title),
            *theme_headers(),
        ),
        Body(
            *body,
            cls="bg-background text-foreground",
            data_event_id=str(event_id) if event_id is not None else None,
        ),
    )


def DetailsMenu(event_id: int, active_link: str, keys: tuple[str, ...]):
    from fasthtml.common import Details, Summary

    return Details(
        Summary("More", cls="nav-link"),
        *_grouped_nav(event_id, active_link, keys),
        cls="more-menu mobile-only",
    )


def page_header(title: str, detail: str = ""):
    from monsterui.franken import H1

    return Div(
        H1(title),
        P(detail) if detail else "",
        cls="page-header",
    )


def status_banner(message: str, tone: str = "info"):
    if not message:
        return ""
    if tone not in {"info", "warning", "error"}:
        tone = "info"
    return Div(
        P(message),
        Button(
            "×",
            type="button",
            cls="toast-close",
            aria_label="Dismiss",
            onclick="this.closest('.toast').remove()",
        ),
        cls=f"toast toast-{tone}",
        role="alert" if tone == "error" else "status",
    )


PAGE_SIZE = 20


def list_pagination(list_id: str, total: int):
    from monsterui.franken import ButtonT, DivLAligned, TextT, UkIconLink

    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    def control(icon: str, action: str, label: str, *, disabled: bool = False):
        return UkIconLink(
            icon,
            button=True,
            type="button",
            cls=("uk-btn", ButtonT.ghost, ButtonT.icon, "icon-btn"),
            aria_label=label,
            data_page=action,
            data_list=list_id,
            disabled=True if disabled else None,
            onclick="changePage(this)",
        )

    return DivLAligned(
        Span(f"Page 1 of {pages}", cls=TextT.sm, data_page_label=list_id),
        DivLAligned(
            control("chevrons-left", "first", "First page", disabled=True),
            control("chevron-left", "prev", "Previous page", disabled=True),
            control("chevron-right", "next", "Next page", disabled=pages <= 1),
            control("chevrons-right", "last", "Last page", disabled=pages <= 1),
            cls="pagination-controls",
        ),
        cls="list-pagination",
        data_page_bar=list_id,
        data_list=list_id,
        data_page_size=str(PAGE_SIZE),
    )


def paged_list(list_id: str, rows: list, empty_message: str):
    if not rows:
        return P(empty_message, cls="empty-note")
    for index, row in enumerate(rows):
        row.attrs["data-page-match"] = "1"
        if index >= PAGE_SIZE:
            row.attrs["hidden"] = True
    return Div(
        Ul(*rows, id=list_id or None, cls="uk-list uk-list-divider"),
        list_pagination(list_id, len(rows)),
    )


def record_list(records: list[dict], empty_message: str, render_record, list_id: str = ""):
    return paged_list(
        list_id,
        [render_record(record) for record in records],
        empty_message,
    )


def stat_card(value, label: str):
    from monsterui.franken import H2 as CardHeading
    from monsterui.franken import Card

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


def live_quote(draw: dict) -> str | None:
    drawn_at = datetime.fromisoformat(draw["created_at"])
    if drawn_at.tzinfo is None:
        drawn_at = drawn_at.replace(tzinfo=UTC)
    elapsed = datetime.now(UTC) - drawn_at.astimezone(UTC)
    quote_interval = int(elapsed // timedelta(minutes=3))
    if quote_interval < 1:
        return None
    quote_order = list(TECHNOLOGY_QUOTES)
    random.Random(str(draw["id"])).shuffle(quote_order)
    return quote_order[(quote_interval - 1) % len(quote_order)]


def winner_fragment(draw: dict | None):
    if draw is None:
        return Div(
            P("The next name could be yours.", cls="live-idle"),
            id="live-result",
            cls="live-result",
            data_draw_id="",
            data_result_version="",
            data_display_state="idle",
        )
    quote = live_quote(draw)
    if quote:
        return Div(
            P(f'"{quote}"', cls="live-quote"),
            id="live-result",
            cls="live-result",
            data_draw_id=str(draw["id"]),
            data_result_version=draw["created_at"],
            data_display_state="quote",
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
        data_display_state="winner",
    )


def emphasized(value: str) -> str:
    return f"<strong>{escape(value)}</strong>"


def confirm_dialog():
    return Dialog(
        H2("Confirm removal", id="confirm-delete-title", cls="dialog-title"),
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


def _draw_confirmation_message(prize: dict, winner: dict):
    message = [Strong(winner["name"])]
    if winner["organization"]:
        message.extend([" from ", Strong(winner["organization"])])
    message.extend([" has been selected for ", Strong(prize["prize_name"])])
    if prize["sponsor"]:
        message.extend([", sponsored by ", Strong(prize["sponsor"])])
    message.append(".")
    return P(*message)


def draw_preview_modal(
    event_id: int, prize_id: int, winner_id: int, prize: dict, winner: dict
):
    return Div(
        Dialog(
            Button(
                "×",
                type="button",
                cls="dialog-close",
                aria_label="Close",
                onclick="this.closest('dialog').close()",
            ),
            H2("Confirm draw", cls="dialog-title"),
            _draw_confirmation_message(prize, winner),
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
