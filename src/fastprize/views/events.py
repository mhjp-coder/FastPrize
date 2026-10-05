from fasthtml.common import (
    H1,
    H2,
    A,
    Button,
    Div,
    Form,
    Img,
    Input,
    Option,
    P,
    Section,
    Select,
    Span,
    Strong,
)
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse

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
        return document(
            "FastPrize | Home",
            Section(
                Img(
                    src="https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=2200&q=85",
                    alt="A lively conference crowd gathered for a stage event",
                    style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;",
                ),
                Div(style="position:absolute;inset:0;background:rgba(17,34,36,.52);"),
                Div(
                    P(
                        "THE RAFFLE, WITHOUT THE FISHBOWL",
                        style="font-size:14px;font-weight:700;letter-spacing:1px;",
                    ),
                    H1(
                        "FastPrize",
                        style="font-family:Georgia,serif;font-size:62px;line-height:1.05;margin:16px 0;",
                    ),
                    P(
                        "No folded slips. No suspiciously convenient hand in the bowl. Just one very surprised winner.",
                        style="font-size:21px;line-height:1.45;max-width:620px;",
                    ),
                    A(
                        "See the events",
                        href="/events",
                        class_="button",
                        style="margin-top:20px;",
                    ),
                    style="position:relative;z-index:1;max-width:720px;",
                ),
                style="position:relative;isolation:isolate;display:flex;align-items:center;min-height:72vh;overflow:hidden;padding:48px 32px;color:white;background:#183f40;",
            ),
            P(
                "Confetti optional. Suspiciously good luck is not.",
                style="font-family:Georgia,serif;font-size:22px;padding:16px 8px;",
            ),
            event_id=selected_event["id"] if selected_event else None,
            event_name=selected_event["name"] if selected_event else None,
        )

    @rt("/events", methods=["GET"])
    def events_page(req: Request):
        selected_event = _selected_event(req, store)
        events = store.list_events()
        event_links = [
            A(
                Div(Strong(event["name"]), Span("Open event workspace")),
                Span("Open"),
                href=f"/events/{event['id']}",
                class_="event-link",
            )
            for event in events
        ]
        return document(
            "FastPrize | Events",
            Div(
                Div("EVENTS", class_="eyebrow"),
                H1("Choose your event."),
                P("Pick up where the suspense left off, or start a new one."),
                class_="page-intro",
            ),
            Section(
                H2("Your events"),
                Div(*event_links, class_="event-grid")
                if event_links
                else P(
                    "No events yet. Create one to start adding entrants and prizes.",
                    class_="empty",
                ),
            ),
            Form(
                Input(
                    name="name", placeholder="Conference or event name", required=True
                ),
                Button("Create event", type="submit"),
                action="/events",
                method="post",
                class_="create-event",
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
                Div("EVENT MANAGEMENT", class_="eyebrow"),
                H1(event["name"]),
                P(
                    f"{eligible_count} eligible entrants | {available_count} prizes available"
                ),
                class_="event-heading",
            ),
            P(message, class_="notice") if message else "",
            A(
                "Open projector display",
                href=f"/events/{event_id}/display",
                class_="button display-link",
            ),
            Section(
                H2("Winner eligibility"),
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
                    ),
                    Button("Save setting", type="submit", class_="secondary"),
                    action=f"/events/{event_id}/settings",
                    method="post",
                ),
                class_="section",
            ),
            Section(
                H2("Data management"),
                P("Remove all entrants and prizes from this event."),
                Form(
                    Button(
                        "Clear all entrants and prizes",
                        type="submit",
                        class_="danger",
                    ),
                    action=f"/events/{event_id}/clear-data",
                    method="post",
                ),
                class_="section",
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="events",
        )

    @rt("/events/{event_id}/settings", methods=["POST"])
    def update_settings(event_id: int, remove_winners: int):
        store.set_remove_winners(event_id, bool(remove_winners))
        return redirect_event(event_id, "settings-updated")

    @rt("/events/{event_id}/clear-data", methods=["POST"])
    def clear_all_data(event_id: int):
        store.clear_all_event_data(event_id)
        return redirect_event(event_id, "data-cleared")
