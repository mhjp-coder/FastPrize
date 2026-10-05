from urllib.parse import quote

from fasthtml.common import (
    A,
    Aside,
    Body,
    Button,
    Div,
    Form,
    H1,
    H2,
    Head,
    Html,
    Input,
    Li,
    Link,
    Main,
    Meta,
    Nav,
    P,
    Script,
    Small,
    Span,
    Strong,
    Title,
    Ul,
)
from starlette.responses import RedirectResponse


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
    page_links = [
        ("Events", "events", "/events"),
        ("Import", "import", "/import"),
        ("Entrants", "entrants", "/entrants"),
        ("Prizes", "prizes", "/prizes"),
        ("Draw", "draw", "/draw"),
        ("Draw history", "history", "/history"),
    ]
    navigation = []
    for label, key, suffix in page_links:
        if event_id is None and key != "events":
            continue
        href = suffix if key == "events" else f"/events/{event_id}{suffix}"
        navigation.append(
            Li(
                A(
                    label,
                    href=href,
                    aria_current="page" if active_link == key else None,
                )
            )
        )
    body_content = (
        content
        if screen
        else (
            Div(
                Aside(
                    A(Strong("F"), " FastPrize", href="/"),
                    P(event_name or "Workspace"),
                    Nav(Ul(*navigation)),
                ),
                Main(*content),
                class_="grid",
            ),
        )
    )
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
        Body(*body_content, class_="screen" if screen else "app"),
    )


def record_list(records: list[dict], empty_message: str, render_record):
    if not records:
        return P(empty_message, class_="empty")
    return Div(*(render_record(record) for record in records), class_="record-list")


def winner_fragment(draw: dict | None):
    if draw is None:
        return Div(
            P("The next name could be yours.", class_="screen-idle"),
            id="live-result",
            **{"data-draw-id": ""},
        )
    return Div(
        Div("The winner is", class_="eyebrow"),
        H1(draw["entrant_name"], class_="winner-name"),
        P(draw["organization"] or "", class_="winner-org"),
        Div(
            Strong(draw["prize_name"]),
            Span("from"),
            Strong(draw["sponsor"] or "our conference sponsors"),
            class_="award-line",
        ),
        id="live-result",
        **{"data-draw-id": str(draw["id"])},
        **{"data-result-version": draw["created_at"]},
    )


def draw_preview_modal(
    event_id: int, prize_id: int, winner_id: int, prize: dict, winner: dict
):
    return Div(
        Div(
            H2("Confirm draw"),
            P(
                f"{winner['name']} from {winner['organization'] or 'an unlisted organization'} has been selected for {prize['prize_name']}."
            ),
            Div(
                Form(
                    Input(type="hidden", name="winner", value=str(winner_id)),
                    Button("Award winner", type="submit"),
                    action=f"/events/{event_id}/draws/{prize_id}/award",
                    method="post",
                ),
                Form(
                    Button("Redraw", type="submit", class_="secondary"),
                    action=f"/events/{event_id}/draws/{prize_id}/preview",
                    method="post",
                ),
                class_="modal-actions",
            ),
            class_="modal-card",
        ),
        class_="modal-backdrop",
    )
