import json
from urllib.parse import quote

from fasthtml.common import (
    H1,
    H2,
    A,
    Body,
    Button,
    Dialog,
    Div,
    Form,
    Head,
    Header,
    Html,
    I,
    Input,
    Link,
    Main,
    Meta,
    Nav,
    P,
    RedirectResponse,
    Script,
    Span,
    Strong,
    Title,
    Ul,
)

EVENT_SELECTION_COOKIE = "fastprize_event_id"


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


def document(
    title: str,
    *content,
    screen: bool = False,
    event_id: int | None = None,
    event_name: str | None = None,
    active_link: str = "",
):
    if screen:
        body_content = (Main(*content, cls="responsive center-align padding"),)
        body_class = "dark compact"
    else:
        page_links = [("All events", "events", "/events", "calendar_month")]
        if event_id is not None:
            page_links.extend(
                [
                    ("Overview", "overview", f"/events/{event_id}", "dashboard"),
                    ("Entrants", "entrants", f"/events/{event_id}/entrants", "groups"),
                    ("Prizes", "prizes", f"/events/{event_id}/prizes", "redeem"),
                    (
                        "Import CSV",
                        "import",
                        f"/events/{event_id}/import",
                        "upload_file",
                    ),
                    ("Draw", "draw", f"/events/{event_id}/draw", "casino"),
                    (
                        "Draw history",
                        "history",
                        f"/events/{event_id}/history",
                        "history",
                    ),
                ]
            )
        navigation = [
            A(
                I(icon),
                label,
                href=href,
                cls="active" if active_link == key else None,
                aria_current="page" if active_link == key else None,
            )
            for label, key, href, icon in page_links
        ]
        brand = A(
            I("casino"),
            Strong("FastPrize"),
            href="/",
        )
        body_content = (
            Nav(
                brand,
                P("CURRENT EVENT", cls="upper small-text"),
                Strong(event_name or "Choose an event"),
                P("WORKSPACE", cls="upper small-text"),
                Div(
                    *navigation,
                    cls="vertical",
                ),
                cls="left m l vertical padding",
            ),
            Nav(
                brand,
                A(I("calendar_month"), "Events", href="/events"),
                cls="top s",
            ),
            Header(
                Div(
                    P("WORKSPACE", cls="upper small-text"),
                    Strong(event_name or "Prize draw operations"),
                ),
                A("All events", href="/events", cls="link"),
            ),
            Main(*content, cls="responsive"),
        )
        body_class = "light compact"
    return Html(
        Head(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title(title),
            Link(
                rel="stylesheet",
                href="https://cdn.jsdelivr.net/npm/beercss@5.0.3/dist/cdn/beer.min.css",
            ),
            Script(
                src="https://cdn.jsdelivr.net/npm/beercss@5.0.3/dist/cdn/beer.min.js",
                type="module",
            ),
        ),
        Body(*body_content, cls=body_class),
    )


def record_list(records: list[dict], empty_message: str, render_record):
    if not records:
        return P(empty_message, cls="surface-variant padding")
    return Ul(*(render_record(record) for record in records), cls="border no-space")


def winner_fragment(draw: dict | None):
    if draw is None:
        return Div(
            P("The next name could be yours.", cls="large-text center-align"),
            id="live-result",
            data_draw_id="",
        )
    return Div(
        P("The winner is", cls="upper small-text tertiary-text center-align"),
        H1(draw["entrant_name"], cls="center-align"),
        P(draw["organization"] or "", cls="medium-text center-align"),
        Div(
            Strong(draw["prize_name"]),
            Span("from"),
            Strong(draw["sponsor"] or "our conference sponsors"),
            cls="horizontal center-align",
        ),
        id="live-result",
        data_draw_id=str(draw["id"]),
        data_result_version=draw["created_at"],
    )


def draw_preview_modal(
    event_id: int, prize_id: int, winner_id: int, prize: dict, winner: dict
):
    return Dialog(
        H2("Confirm draw"),
        P(
            f"{winner['name']} from {winner['organization'] or 'an unlisted organization'} has been selected for {prize['prize_name']}."
        ),
        Nav(
            Form(
                Input(type="hidden", name="winner", value=str(winner_id)),
                Button("Award winner", type="submit", cls="primary"),
                action=f"/events/{event_id}/draws/{prize_id}/award",
                method="post",
            ),
            Form(
                Button("Redraw", type="submit", cls="secondary"),
                action=f"/events/{event_id}/draws/{prize_id}/preview",
                method="post",
            ),
            cls="horizontal",
        ),
        open=True,
        cls="modal medium padding",
    )
