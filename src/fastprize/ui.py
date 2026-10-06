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
    Footer,
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
    fhjsscr,
    htmxsrc,
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
    "data-cleared": "Data cleared",
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
        body_content = (
            Main(
                *content,
                cls="responsive center-align padding",
                style="display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 100vh",
            ),
        )
        body_class = "dark"
    else:
        page_links = [("Events", "events", "/events", "calendar_month")]
        if event_id is not None:
            page_links.extend(
                [
                    ("Manage", "overview", f"/events/{event_id}", "dashboard"),
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
                I(
                    icon,
                    style=(
                        "font-variation-settings: 'FILL' 0; color: var(--primary)"
                        if active_link == key
                        else "font-variation-settings: 'FILL' 0"
                    ),
                ),
                Div(label),
                href=href,
                cls="active bottom-margin" if active_link == key else "bottom-margin",
                style="--_margin: 0.25rem",
                aria_current="page" if active_link == key else None,
            )
            for label, key, href, icon in page_links
        ]
        mobile_navigation = [
            A(
                I(
                    icon,
                    style=(
                        "font-variation-settings: 'FILL' 0; color: var(--primary)"
                        if active_link == key
                        else "font-variation-settings: 'FILL' 0"
                    ),
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
            return Div(
                role="img",
                aria_label="FastPrize logo",
                style=f"width: {width}px; height: {height}px; border-radius: 0; background-color: var(--primary); mask: url('/assets/fastprize-logo.svg') center / contain no-repeat; -webkit-mask: url('/assets/fastprize-logo.svg') center / contain no-repeat",
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
            style="width: 88px; height: 88px; padding: 0; display: flex; align-items: center; justify-content: center; border-radius: 50%",
        )
        body_content = (
            Nav(
                Div(sidebar_brand, style="margin-bottom: 1rem"),
                *navigation,
                cls="left drawer large-padding max m l surface-container",
                style="width: 14rem; min-width: 14rem",
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
                        onclick="""
                            const nextMode = ui('mode') === 'dark' ? 'light' : 'dark';
                            ui('mode', nextMode);
                            localStorage.setItem('theme-mode', nextMode);
                            window.updateFastPrizeBrandTheme();
                        """,
                        cls="circle flat large",
                    ),
                    Button(
                        Span(),
                        type="button",
                        title="Teal theme",
                        aria_label="Use teal theme",
                        onclick="window.setFastPrizeTheme('#009688')",
                        cls="circle",
                        style="background-color: #009688",
                    ),
                    Button(
                        Span(),
                        type="button",
                        title="Amber theme",
                        aria_label="Use amber theme",
                        onclick="window.setFastPrizeTheme('#ffc107')",
                        cls="circle",
                        style="background-color: #ffc107",
                    ),
                    Button(
                        Span(),
                        type="button",
                        title="Blue theme",
                        aria_label="Use blue theme",
                        onclick="window.setFastPrizeTheme('#0277bd')",
                        cls="circle",
                        style="background-color: #0277bd",
                    ),
                    cls="horizontal middle-align small-space",
                ),
                cls="large-padding horizontal wrap middle-align",
                style="display: flex; justify-content: flex-end",
            ),
            Main(*content, cls="responsive large-padding"),
            Div(cls="s", style="height: 5rem"),
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
            Link(rel="preconnect", href="https://fonts.googleapis.com"),
            Link(
                rel="preconnect",
                href="https://fonts.gstatic.com",
                crossorigin="anonymous",
            ),
            Link(
                rel="stylesheet",
                href="https://fonts.googleapis.com/css2?family=Roboto+Flex:opsz,wght@8..144,100..1000&display=swap",
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
            Script("""
                let faviconSourcePromise;
                window.updateFastPrizeBrandTheme = async () => {
                    const favicon = document.querySelector('link[rel="icon"]');
                    if (!favicon) return;
                    faviconSourcePromise ||= fetch('/assets/fastprize-favicon.svg')
                        .then(response => response.ok ? response.text() : '');
                    const source = await faviconSourcePromise;
                    if (!source) return;
                    const styles = getComputedStyle(document.body);
                    const primary = styles.getPropertyValue('--primary').trim();
                    const onPrimary = styles.getPropertyValue('--on-primary').trim();
                    const themedIcon = source
                        .replace('#245f83', primary)
                        .replace('#ffffff', onPrimary);
                    favicon.href = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(themedIcon)}`;
                };
                window.setFastPrizeTheme = async (color) => {
                    await ui('theme', color);
                    localStorage.setItem('theme-color', color);
                    await window.updateFastPrizeBrandTheme();
                };
                document.addEventListener('DOMContentLoaded', async () => {
                    const savedMode = localStorage.getItem('theme-mode') || 'light';
                    const savedColor = localStorage.getItem('theme-color') || '#009688';
                    if (!document.body.classList.contains('dark')) {
                        ui('mode', savedMode);
                    }
                    await ui('theme', savedColor);
                    await window.updateFastPrizeBrandTheme();
                });
            """),
        ),
        Body(*body_content, cls=body_class),
        style="--font: 'Roboto Flex', sans-serif",
    )


def record_list(records: list[dict], empty_message: str, render_record):
    if not records:
        return P(empty_message, cls="surface-variant padding")
    return Ul(*(render_record(record) for record in records), cls="border no-space")


def winner_fragment(draw: dict | None):
    if draw is None:
        return Div(
            H1("The next name could be yours.", cls="center-align"),
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
