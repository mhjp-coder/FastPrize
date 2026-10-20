from fasthtml.common import (
    A,
    Div,
    HTTPException,
    Label,
    RedirectResponse,
    Request,
    Span,
)
from monsterui.franken import (
    H2,
    Button,
    ButtonT,
    Card,
    FlexT,
    Form,
    Grid,
    Input,
    P,
    Placeholder,
    Switch,
)

from fastprize.ui import (
    EVENT_SELECTION_COOKIE,
    document,
    emphasized,
    hstack,
    page_header,
    redirect_event,
    stat_card,
    status_banner,
    status_message,
    status_tone,
    vstack,
)
from fastprize.views.imports import import_form


def _selected_event(req: Request, store) -> dict | None:
    value = req.cookies.get(EVENT_SELECTION_COOKIE)
    if value is None:
        return None
    try:
        event_id = int(value)
    except ValueError:
        return None
    return store.get_event(event_id)


def _event_card(event: dict):
    return A(
        Card(H2(event["name"])),
        href=f"/events/{event['id']}",
        cls="block no-underline text-inherit",
    )


def _events_list(events: list[dict]):
    event_links = [_event_card(event) for event in events]
    return vstack(
        H2("Your events"),
        Grid(*event_links, cols=2, cls="gap-6")
        if event_links
        else Placeholder(
            P("No events yet. Create one to start adding entrants and prizes."),
        ),
    )


def _desk_status(entrant_count: int, prize_count: int) -> str:
    if entrant_count and prize_count:
        return "Your draw desk is ready."
    missing = []
    if not entrant_count:
        missing.append("entrants")
    if not prize_count:
        missing.append("prizes")
    subject = " or ".join(missing)
    return f"This event has no {subject} yet."


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
            selected_panel = vstack(
                Card(
                    P("Current event", cls="nav-label"),
                    H2(selected_event["name"]),
                    P(_desk_status(len(entrants), len(prizes))),
                    DivActions(
                        A(
                            "Manage Event",
                            href=f"/events/{selected_event['id']}",
                            cls="uk-btn uk-btn-primary",
                        ),
                        Button(
                            "Live Display",
                            type="button",
                            cls=ButtonT.primary,
                            onclick="openDisplayLink()",
                        ),
                    ),
                ),
                Grid(
                    Card(H2(str(eligible_count)), P("eligible entrants"), cls="h-full"),
                    Card(H2(str(available_count)), P("prizes available"), cls="h-full"),
                    cols=2,
                    cls="gap-6",
                ),
            )
        return document(
            "FastPrize",
            page_header(
                "FastPrize",
                "No folded slips. No guesswork. Keep every event, entrant, prize, and result in view.",
            ),
            selected_panel or _events_list(store.list_events()),
            event_id=selected_event["id"] if selected_event else None,
            event_name=selected_event["name"] if selected_event else None,
        )

    @rt("/events", methods=["GET"])
    def events_page(req: Request):
        selected_event = _selected_event(req, store)
        return document(
            "FastPrize | Events",
            page_header(
                "Choose your event.",
                "Pick up where the suspense left off, or start a new one.",
            ),
            _events_list(store.list_events()),
            Form(
                Div(
                    Input(
                        name="name",
                        placeholder="Conference or event name",
                        required=True,
                        type="text",
                    ),
                    Button("Create event", cls=ButtonT.primary),
                    cls="grid grid-cols-1 items-end gap-6 md:grid-cols-2",
                ),
                action="/events",
                method="post",
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
            page_header(event["name"]),
            status_banner(message, status_tone(status)),
            Grid(
                stat_card(eligible_count, "eligible entrants"),
                stat_card(available_count, "prizes available"),
                cols_max=2,
                cls="gap-6",
            ),
            Card(
                H2("Winner eligibility"),
                P("Winners are removed from future draws?"),
                Form(
                    Input(type="hidden", name="remove_winners", value="0"),
                    Label(
                        Switch(
                            name="remove_winners",
                            value="1",
                            checked=bool(event["remove_winners"]) or None,
                            id="remove_winners",
                            onchange="this.form.requestSubmit()",
                        ),
                        Span("Yes" if event["remove_winners"] else "No"),
                        fr="remove_winners",
                        cls=(FlexT.inline, FlexT.middle, "w-fit cursor-pointer gap-3"),
                    ),
                    action=f"/events/{event_id}/settings",
                    method="post",
                ),
            ),
            import_form(event_id),
            Card(
                H2("Data management"),
                DivActions(
                    Button(
                        "Clear all entrants and prizes",
                        type="button",
                        cls=ButtonT.destructive,
                        data_confirm=(
                            "Clear all entrants and prizes from "
                            f"{emphasized(event['name'])}? This cannot be undone."
                        ),
                        data_confirm_action=f"/events/{event_id}/clear-data",
                        data_confirm_label="Clear all",
                        onclick="confirmDelete(this)",
                    ),
                    Button(
                        "Delete event",
                        type="button",
                        cls=ButtonT.destructive,
                        data_confirm=(
                            f"Delete {emphasized(event['name'])}? This removes the event and its "
                            "entrants, prizes, and draw history. This cannot be undone."
                        ),
                        data_confirm_action=f"/events/{event_id}/delete",
                        data_confirm_label="Delete event",
                        onclick="confirmDelete(this)",
                    ),
                ),
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="overview",
        )

    @rt("/events/{event_id}/settings", methods=["POST"])
    async def update_settings(event_id: int, req: Request):
        form = await req.form()
        enabled = "1" in {str(value) for value in form.getlist("remove_winners")}
        store.set_remove_winners(event_id, enabled)
        return redirect_event(event_id, "settings-updated")

    @rt("/events/{event_id}/clear-data", methods=["POST"])
    def clear_all_data(event_id: int):
        store.clear_all_event_data(event_id)
        return redirect_event(event_id, "data-cleared")

    @rt("/events/{event_id}/delete", methods=["POST"])
    def delete_event(event_id: int):
        store.delete_event(event_id)
        response = RedirectResponse("/events", status_code=303)
        response.delete_cookie(EVENT_SELECTION_COOKIE, path="/")
        return response


def DivActions(*children, cls=()):
    return hstack(*children, cls=cls)
