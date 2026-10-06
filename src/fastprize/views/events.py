from fasthtml.common import (
    H1,
    H2,
    A,
    Article,
    Button,
    Div,
    Form,
    Hr,
    HTTPException,
    I,
    Input,
    Label,
    P,
    RedirectResponse,
    Request,
    Section,
    Span,
    Strong,
)

from fastprize.ui import (
    EVENT_SELECTION_COOKIE,
    document,
    redirect_event,
    status_message,
)


def _selected_event(req: Request, store) -> dict | None:
    value = req.cookies.get(EVENT_SELECTION_COOKIE)
    if value is None:
        return None
    try:
        event_id = int(value)
    except ValueError:
        return None
    return store.get_event(event_id)


def register_routes(rt, store):
    @rt("/")
    def home(req: Request):
        selected_event = _selected_event(req, store)
        selected_panel = None
        if selected_event:
            entrants = store.entrants(selected_event["id"])
            prizes = store.prizes(selected_event["id"])
            eligible_count = sum(entrant["eligible"] for entrant in entrants)
            available_count = sum(not prize["drawn"] for prize in prizes)
            if eligible_count and available_count:
                readiness_message = "You are Ready to Draw!"
            else:
                missing_items = []
                if not eligible_count:
                    missing_items.append("eligible entrants")
                if not available_count:
                    missing_items.append("prizes")
                readiness_message = f"Add {' and '.join(missing_items)} to get started."
            workspace_ready = bool(eligible_count and available_count)
            workspace_href = f"/events/{selected_event['id']}/{'draw' if workspace_ready else 'import'}"
            workspace_icon = "casino" if workspace_ready else "upload_file"
            workspace_label = "Draw" if workspace_ready else "Import CSV"
            selected_panel = Section(
                Article(
                    Div(
                        Div("CURRENT EVENT", cls="upper small-text secondary-text"),
                        H2(selected_event["name"], cls="small"),
                        P(readiness_message),
                    ),
                    Div(
                        A(
                            I(workspace_icon),
                            Span(workspace_label),
                            href=workspace_href,
                            cls="button primary m6 responsive extra",
                        ),
                        A(
                            I("present_to_all"),
                            Span("Open projector display"),
                            href=f"/events/{selected_event['id']}/display",
                            cls="button secondary m6 responsive extra",
                        ),
                        cls="grid middle-align",
                    ),
                    cls="card padding tertiary-container small-round",
                ),
                Div(
                    Article(
                        P(Strong(str(eligible_count))),
                        P("eligible entrants"),
                        cls="s6 m6 l6 card padding fill small-round",
                    ),
                    Article(
                        P(Strong(str(available_count))),
                        P("prizes available"),
                        cls="s6 m6 l6 card padding fill small-round",
                    ),
                    cls="grid",
                ),
            )
        return document(
            "FastPrize | Draw Center",
            Div(
                H1("Draw Center", cls="small"),
                P(
                    "Hats are for pulling rabbits, not folded slips. We do it pseudo-randomly."
                ),
                cls="vertical",
            ),
            selected_panel
            or P(
                "Choose an event to open its workspace, or create one to get started.",
                cls="surface-variant padding",
            ),
            event_id=selected_event["id"] if selected_event else None,
            event_name=selected_event["name"] if selected_event else None,
        )

    @rt("/events", methods=["GET"])
    def events_page(req: Request):
        selected_event = _selected_event(req, store)
        events = store.list_events()
        event_links = [
            Article(
                A(
                    H2(event["name"], cls="small"),
                    href=f"/events/{event['id']}",
                    cls="link responsive center-align",
                ),
                cls="s12 m6 l4 card padding small-round",
            )
            for event in events
        ]
        return document(
            "FastPrize | Events",
            Div(
                H1("Choose your event.", cls="small"),
                P("Pick up where the suspense left off, or start a new one."),
                cls="vertical bottom-padding",
            ),
            Hr(cls="medium-divider"),
            H2("Create an event", cls="small"),
            Form(
                Div(
                    Input(
                        id="event-name",
                        name="name",
                        required=True,
                        type="text",
                    ),
                    Label("Event name", fr="event-name"),
                    cls="m7 field label border round fill extra",
                ),
                Button(
                    I("add"),
                    Span("Create event"),
                    type="submit",
                    cls="m5 responsive fill extra",
                ),
                action="/events",
                method="post",
                cls="grid bottom-padding",
            ),
            Hr(cls="medium-divider"),
            Section(
                H2("Your events", cls="small"),
                Div(*event_links, cls="grid")
                if event_links
                else P(
                    "No events yet. Create one to start adding entrants and prizes.",
                    cls="surface-variant padding",
                ),
            ),
            Hr(cls="medium-divider"),
            event_id=selected_event["id"] if selected_event else None,
            event_name=selected_event["name"] if selected_event else None,
            active_link="events",
        )

    @rt("/events", methods=["POST"])
    def create_event(name: str):
        try:
            event_id = store.create_event(name)
        except ValueError:
            return RedirectResponse("/events", status_code=303)
        return redirect_event(event_id, "event-created")

    @rt("/events/{event_id}")
    def event_workspace(event_id: int, status: str = ""):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        entrants = store.entrants(event_id)
        prizes = store.prizes(event_id)
        eligible_count = sum(entrant["eligible"] for entrant in entrants)
        available_count = sum(not prize["drawn"] for prize in prizes)
        message = status_message(status)
        clear_notice = message if status == "data-cleared" else ""
        return document(
            f"FastPrize | {event['name']} | Events",
            Div(
                H1(event["name"], cls="small"),
                Div(
                    Article(
                        H2("Entrants", cls="small"),
                        Div(
                            Div(P(Strong(str(len(entrants)))), P("total"), cls="s6"),
                            Div(
                                P(Strong(str(eligible_count))), P("eligible"), cls="s6"
                            ),
                            cls="grid",
                        ),
                        cls="s12 m6 l6 card padding fill small-round",
                    ),
                    Article(
                        H2("Prizes", cls="small"),
                        Div(
                            Div(P(Strong(str(len(prizes)))), P("total"), cls="s6"),
                            Div(
                                P(Strong(str(available_count))),
                                P("available"),
                                cls="s6",
                            ),
                            cls="grid",
                        ),
                        cls="s12 m6 l6 card padding fill small-round",
                    ),
                    cls="grid",
                ),
                cls="vertical bottom-padding",
            ),
            P(message, cls="tertiary-container padding")
            if message and not clear_notice
            else "",
            Section(
                H2("Winner eligibility", cls="small"),
                Form(
                    Label(
                        Input(
                            type="checkbox",
                            name="remove_winners",
                            id="remove_winners",
                            value="1",
                            checked=bool(event["remove_winners"]),
                            aria_label="Remove winners from future draws",
                            hx_post=f"/events/{event_id}/settings",
                            hx_trigger="change",
                            hx_target="#remove-winners-help",
                            hx_swap="outerHTML",
                        ),
                        Span(),
                        cls="switch",
                    ),
                    P(
                        "Drawn winners are removed from future draws."
                        if event["remove_winners"]
                        else "Previous winners remain eligible.",
                        id="remove-winners-help",
                        cls="large-text secondary-text",
                    ),
                    action=f"/events/{event_id}/settings",
                    method="post",
                    cls="horizontal middle-align",
                ),
                cls="vertical bottom-padding",
            ),
            Section(
                H2("Data management", cls="small"),
                P("Remove all entrants and prizes from this event."),
                Div(
                    Form(
                        Button(
                            I("delete"),
                            Span("Clear all entrants and prizes"),
                            type="submit",
                            cls="s12 responsive extra error",
                        ),
                        action=f"/events/{event_id}/clear-data",
                        method="post",
                        onsubmit="return confirm('Clear all entrants and prizes? This cannot be undone.');",
                        cls="s12 grid",
                    ),
                    Span(
                        clear_notice,
                        cls="s12 chip tertiary",
                        role="status",
                        aria_live="polite",
                    )
                    if clear_notice
                    else "",
                    cls="grid middle-align",
                ),
                cls="vertical",
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="overview",
        )

    @rt("/events/{event_id}/settings", methods=["POST"])
    def update_settings(event_id: int, req: Request, remove_winners: int = 0):
        store.set_remove_winners(event_id, bool(remove_winners))
        if req.headers.get("HX-Request") == "true":
            helper_text = (
                "Drawn winners are removed from future draws."
                if remove_winners
                else "Previous winners remain eligible."
            )
            return P(
                helper_text,
                id="remove-winners-help",
                cls="large-text secondary-text",
            )
        return RedirectResponse(f"/events/{event_id}", status_code=303)

    @rt("/events/{event_id}/clear-data", methods=["POST"])
    def clear_all_data(event_id: int):
        store.clear_all_event_data(event_id)
        return redirect_event(event_id, "data-cleared")
