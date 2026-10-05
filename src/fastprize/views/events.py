from fasthtml.common import (
    H1,
    H2,
    A,
    Article,
    Button,
    Div,
    Form,
    HTTPException,
    Input,
    Option,
    P,
    RedirectResponse,
    Request,
    Section,
    Select,
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
        available_events = store.list_events()
        event_links = [
            Article(
                A(
                    H2(event["name"], cls="small"),
                    href=f"/events/{event['id']}",
                    cls="link responsive center-align",
                ),
                cls="s12 m6 l4 card padding small-round",
            )
            for event in available_events
        ]
        selected_panel = None
        if selected_event:
            entrants = store.entrants(selected_event["id"])
            prizes = store.prizes(selected_event["id"])
            eligible_count = sum(entrant["eligible"] for entrant in entrants)
            available_count = sum(not prize["drawn"] for prize in prizes)
            selected_panel = Section(
                Article(
                    Div(
                        Div("CURRENT EVENT", cls="upper small-text secondary-text"),
                        H2(selected_event["name"], cls="small"),
                        P("Your draw desk is ready."),
                    ),
                    Div(
                        A(
                            "Open workspace",
                            href=f"/events/{selected_event['id']}",
                            cls="primary",
                        ),
                        A(
                            "Open projector display",
                            href=f"/events/{selected_event['id']}/display",
                            cls="tertiary",
                        ),
                        cls="horizontal",
                    ),
                    cls="card padding primary-container small-round",
                ),
                Div(
                    Article(
                        P(Strong(str(eligible_count))),
                        P("eligible entrants"),
                        cls="s6 m6 l6 card padding small-round",
                    ),
                    Article(
                        P(Strong(str(available_count))),
                        P("prizes available"),
                        cls="s6 m6 l6 card padding small-round",
                    ),
                    cls="grid",
                ),
            )
        return document(
            "FastPrize | Draw desk",
            Div(
                Div("DRAW OPERATIONS", cls="upper small-text secondary-text"),
                H1("The draw desk", cls="small"),
                P(
                    "No folded slips. No guesswork. Keep every event, entrant, prize, and result in view."
                ),
                cls="vertical",
            ),
            selected_panel
            or P(
                "Choose an event to open its workspace, or create one to get started.",
                cls="surface-variant padding",
            ),
            Section(
                Div(
                    H2("Your events", cls="small"),
                    A("Manage events", href="/events", cls="link"),
                    cls="horizontal middle-align",
                ),
                Div(*event_links, cls="grid")
                if event_links
                else A("Create your first event", href="/events", cls="primary"),
                cls="vertical",
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
                Div("EVENTS", cls="upper small-text secondary-text"),
                H1("Choose your event.", cls="small"),
                P("Pick up where the suspense left off, or start a new one."),
                cls="vertical",
            ),
            Section(
                H2("Your events", cls="small"),
                Div(*event_links, cls="grid")
                if event_links
                else P(
                    "No events yet. Create one to start adding entrants and prizes.",
                    cls="surface-variant padding",
                ),
            ),
            Form(
                Input(
                    name="name",
                    placeholder="Conference or event name",
                    required=True,
                    type="text",
                ),
                Button("Create event", type="submit", cls="s12 m3 l2 primary"),
                action="/events",
                method="post",
                cls="grid",
            ),
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
        return document(
            f"FastPrize | {event['name']} | Events",
            Div(
                Div("EVENT MANAGEMENT", cls="upper small-text secondary-text"),
                H1(event["name"], cls="small"),
                P(
                    f"{eligible_count} eligible entrants | {available_count} prizes available"
                ),
                cls="vertical",
            ),
            P(message, cls="tertiary-container padding") if message else "",
            A(
                "Open projector display",
                href=f"/events/{event_id}/display",
                cls="tertiary",
            ),
            Section(
                H2("Winner eligibility", cls="small"),
                P("Choose whether winners can be selected again."),
                Form(
                    Select(
                        Option(
                            "Remove winner from future draws",
                            value="1",
                            selected=bool(event["remove_winners"]),
                        ),
                        Option(
                            "Keep winner eligible",
                            value="0",
                            selected=not bool(event["remove_winners"]),
                        ),
                        name="remove_winners",
                        id="remove_winners",
                        cls="s12 m8 l8",
                    ),
                    Button("Save setting", type="submit", cls="s12 m4 l4 primary"),
                    action=f"/events/{event_id}/settings",
                    method="post",
                    cls="grid",
                ),
                cls="vertical",
            ),
            Section(
                H2("Data management", cls="small"),
                P("Remove all entrants and prizes from this event."),
                Form(
                    Button(
                        "Clear all entrants and prizes",
                        type="submit",
                        cls="error",
                    ),
                    action=f"/events/{event_id}/clear-data",
                    method="post",
                ),
                cls="vertical",
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="overview",
        )

    @rt("/events/{event_id}/settings", methods=["POST"])
    def update_settings(event_id: int, remove_winners: int):
        store.set_remove_winners(event_id, bool(remove_winners))
        return redirect_event(event_id, "settings-updated")

    @rt("/events/{event_id}/clear-data", methods=["POST"])
    def clear_all_data(event_id: int):
        store.clear_all_event_data(event_id)
        return redirect_event(event_id, "data-cleared")
