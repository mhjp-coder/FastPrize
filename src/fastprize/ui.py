import json
from urllib.parse import quote

from fasthtml.common import (
    H1,
    H2,
    H3,
    A,
    Body,
    Button,
    Dialog,
    Div,
    Footer,
    Form,
    Head,
    Header,
    Html,
    I,
    Img,
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
    fhjsscr,
    htmxsrc,
)
from segno import make as make_qr

EVENT_SELECTION_COOKIE = "fastprize_event_id"


STATUS_MESSAGES = {
    "event-created": "Event created.",
    "entrant-added": "Entrant added.",
    "entrant-missing": "That entrant could not be found.",
    "prize-added": "Prize added.",
    "data-cleared": "Data cleared",
    "entrants-imported": "Entrant CSV imported.",
    "prizes-imported": "Prize CSV imported.",
    "no-eligible-entrants": "Add an eligible entrant before drawing this prize.",
    "no-file": "Choose a CSV file to import.",
    "invalid-entrant": "Entrant name is required, and duplicate names are skipped.",
    "invalid-prize": "Prize name is required.",
    "prize-locked": "Awarded prizes cannot be changed or removed.",
    "prize-returned": "Prize returned to the pool and removed from draw history.",
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
        body_content = (
            Main(
                *content,
                cls="responsive center-align padding vertical middle-align",
            ),
        )
        body_class = "dark"
    else:
        page_links = [("Events", "events", "/events", "calendar_month")]
        if event_id is not None:
            page_links.extend(
                [
                    ("Manage", "overview", f"/events/{event_id}", "event"),
                    ("Entrants", "entrants", f"/events/{event_id}/entrants", "groups"),
                    ("Prizes", "prizes", f"/events/{event_id}/prizes", "redeem"),
                    ("Draw", "draw", f"/events/{event_id}/draw", "casino"),
                    (
                        "Draw history",
                        "history",
                        f"/events/{event_id}/history",
                        "history",
                    ),
                ]
            )
        navigation = []
        for label, key, href, icon in page_links:
            navigation.append(
                A(
                    I(
                        icon,
                        cls="primary-text" if active_link == key else None,
                    ),
                    Div(label),
                    href=href,
                    cls=(
                        "active tiny-margin bottom-margin"
                        if active_link == key
                        else "tiny-margin bottom-margin"
                    ),
                    aria_current="page" if active_link == key else None,
                )
            )
            if key == "draw":
                navigation.append(
                    A(
                        I("qr_code_2"),
                        Div("Live display"),
                        href="#",
                        hx_get=f"/events/{event_id}/display-link",
                        hx_target="#display-link-modal",
                        hx_swap="innerHTML",
                        aria_haspopup="dialog",
                        cls="tiny-margin bottom-margin",
                    )
                )
        mobile_navigation = [
            A(
                I(
                    icon,
                    cls="primary-text" if active_link == key else None,
                ),
                href=href,
                cls=(
                    "max circle transparent active"
                    if active_link == key
                    else "max circle transparent"
                ),
                title=label,
                aria_label=label,
                aria_current="page" if active_link == key else None,
            )
            for label, key, href, icon in page_links
        ]

        def brand_mark(width: int = 96, height: int = 60):
            return Img(
                src="/assets/fastprize-logo.svg",
                alt="FastPrize logo",
                width=width,
                height=height,
            )

        brand = A(
            brand_mark(),
            href="/",
            aria_label="FastPrize home",
        )
        sidebar_brand = A(
            brand_mark(80, 50),
            href="/",
            aria_label="FastPrize home",
            cls="circle",
        )
        body_content = (
            Nav(
                Div(sidebar_brand, cls="bottom-margin"),
                *navigation,
                cls="left drawer large-padding max m l small-width surface-container",
            ),
            Nav(
                brand,
                cls="top s padding",
            ),
            Header(
                Div(
                    Button(
                        I("dark_mode"),
                        type="button",
                        title="Toggle light or dark mode",
                        aria_label="Toggle light or dark mode",
                        data_theme_mode="toggle",
                        cls="circle flat large",
                    ),
                    Button(
                        Span(),
                        type="button",
                        title="Teal theme",
                        aria_label="Use teal theme",
                        data_theme_color="#009688",
                        cls="circle teal",
                    ),
                    Button(
                        Span(),
                        type="button",
                        title="Amber theme",
                        aria_label="Use amber theme",
                        data_theme_color="#ffc107",
                        cls="circle amber",
                    ),
                    Button(
                        Span(),
                        type="button",
                        title="Blue theme",
                        aria_label="Use blue theme",
                        data_theme_color="#0277bd",
                        cls="circle blue",
                    ),
                    cls="horizontal middle-align small-space",
                ),
                cls="large-padding horizontal middle-align right-align responsive",
            ),
            Main(*content, cls="responsive large-padding"),
            Div(id="display-link-modal") if event_id is not None else "",
            Div(cls="extra-space"),
            Footer(
                Nav(*mobile_navigation),
                cls="fill fixed s",
            ),
        )
        body_class = "light"
    return Html(
        Head(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title(title),
            htmxsrc,
            fhjsscr,
            Link(
                rel="icon",
                type="image/svg+xml",
                href="/assets/fastprize-favicon.svg",
            ),
            Link(
                rel="stylesheet",
                href="https://cdn.jsdelivr.net/npm/beercss@5.0.3/dist/cdn/beer.min.css",
            ),
            Script(
                src="https://cdn.jsdelivr.net/npm/material-dynamic-colors@1.1.4/dist/cdn/material-dynamic-colors.min.js",
                type="module",
            ),
            Script(
                src="https://cdn.jsdelivr.net/npm/beercss@5.0.3/dist/cdn/beer.min.js",
                type="module",
            ),
            Script(src="/assets/theme.js?v=2", type="module"),
            Script(src="/assets/interactions.js", type="module"),
        ),
        Body(*body_content, cls=body_class),
    )


def record_list(records: list[dict], empty_message: str, render_record):
    if not records:
        return P(empty_message, cls="surface-variant padding")
    return Ul(*(render_record(record) for record in records), cls="border no-space")


def winner_fragment(draw: dict | None, poll_url: str | None = None):
    poll_attrs = (
        {
            "hx_get": poll_url,
            "hx_trigger": "every 1s",
            "hx_swap": "outerHTML",
        }
        if poll_url
        else {}
    )
    if draw is None:
        return Div(
            H1("The next name could be yours.", cls="center-align"),
            id="live-result",
            data_draw_id="",
            **poll_attrs,
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
        **poll_attrs,
    )


def display_link_modal(display_url: str):
    qr_code = make_qr(display_url, error="m").svg_data_uri(
        scale=8, border=2, dark="black", light="white"
    )
    return Div(
        Dialog(
            H2("Live display", cls="small"),
            P("Scan the QR code or open this link to view the live draw."),
            Div(
                Img(
                    src=qr_code,
                    alt="QR code for the live draw display link",
                    width=240,
                    height=240,
                ),
                cls="center-align",
            ),
            P(A(display_url, href=display_url, target="_blank", rel="noopener")),
            Nav(
                Form(
                    Button("Close", type="submit", cls="text"),
                    method="dialog",
                ),
                cls="horizontal",
            ),
            id="display-link-dialog",
            aria_label="Live draw display link",
            data_auto_open="true",
            cls="modal padding medium-width left-align",
        ),
    )


def draw_preview_modal(
    event_id: int, prize_id: int, winner_id: int, prize: dict, winner: dict
):
    def actions(size: str):
        return (
            Button(
                "Award winner",
                type="submit",
                form="award-draw-form",
                cls=f"{size} primary",
            ),
            Button(
                "Redraw",
                type="submit",
                form="redraw-draw-form",
                cls=f"{size} tertiary",
            ),
            Button(
                "Cancel",
                type="submit",
                form="cancel-draw-form",
                cls=f"{size} error",
            ),
        )

    award, redraw, cancel = actions("extra")
    small_award, small_redraw, small_cancel = actions("large")
    return Div(
        Dialog(
            H2(winner["name"]),
            P(
                winner["organization"] or "No organization listed",
                cls="large-text secondary-text",
            ),
            Div(cls="medium-space"),
            H3(prize["prize_name"]),
            P(
                prize["sponsor"] or "No sponsor listed",
                cls="large-text secondary-text",
            ),
            Div(cls="medium-space"),
            Form(
                Input(type="hidden", name="winner", value=str(winner_id)),
                action=f"/events/{event_id}/draws/{prize_id}/award",
                method="post",
                id="award-draw-form",
                hidden=True,
            ),
            Form(
                action=f"/events/{event_id}/draws/{prize_id}/preview",
                method="post",
                id="redraw-draw-form",
                hidden=True,
            ),
            Form(
                action=f"/events/{event_id}/draw",
                method="get",
                id="cancel-draw-form",
                hidden=True,
            ),
            Div(
                Nav(award, redraw, cls="wrap small-space m8"),
                Nav(cancel, cls="right-align m4"),
                cls="grid top-margin m l",
            ),
            Nav(
                small_award,
                small_redraw,
                small_cancel,
                cls="wrap small-space top-margin s",
            ),
            id="draw-confirmation",
            data_auto_open="true",
            cls="modal padding large-width left-align draw-confirmation",
        ),
    )
