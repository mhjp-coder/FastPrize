from fasthtml.common import (
    H1,
    H2,
    H3,
    A,
    Article,
    Button,
    Details,
    Dialog,
    Div,
    Form,
    HTTPException,
    I,
    Input,
    Label,
    Nav,
    P,
    RedirectResponse,
    Request,
    Section,
    Span,
    Summary,
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
                        Button(
                            I("qr_code_2"),
                            Span("Live display"),
                            type="button",
                            aria_haspopup="dialog",
                            hx_get=f"/events/{selected_event['id']}/display-link",
                            hx_target="#display-link-modal",
                            hx_swap="innerHTML",
                            cls="tertiary m6 responsive extra",
                        ),
                        cls="grid middle-align",
                    ),
                    cls="card padding tertiary-container small-round",
                ),
                Div(
                    Article(
                        H2(str(eligible_count), cls="small"),
                        P("eligible entrants"),
                        cls="s6 m6 l6 card padding fill small-round",
                    ),
                    Article(
                        H2(str(available_count), cls="small"),
                        P("prizes available"),
                        cls="s6 m6 l6 card padding fill small-round",
                    ),
                    cls="grid",
                ),
            )
        return document(
            "FastPrize | Draw Center",
            Article(
                H1("Draw Center", cls="small"),
                P(
                    "Hats are for pulling rabbits, not folded slips. We do it pseudo-randomly."
                ),
                P(
                    "Choose an event to open its workspace, or create one to get started.",
                )
                if not selected_event
                else "",
                cls="card padding primary-container small-round vertical bottom-margin",
            ),
            selected_panel or "",
            A(
                I("add"),
                Span("Create event"),
                href="/events",
                cls="button primary responsive extra bottom-margin",
            )
            if not selected_event and not store.list_events()
            else "",
            event_id=selected_event["id"] if selected_event else None,
            event_name=selected_event["name"] if selected_event else None,
        )

    @rt("/events", methods=["GET"])
    def events_page(req: Request):
        selected_event = _selected_event(req, store)
        events = store.list_events()
        event_links = []
        for event in events:
            is_active = (
                selected_event is not None and event["id"] == selected_event["id"]
            )
            event_links.append(
                A(
                    Div(
                        H3(event["name"], cls="small"),
                        cls="vertical center-align",
                    ),
                    href=f"/events/{event['id']}",
                    cls=(
                        "s12 m6 l4 link responsive center-align padding "
                        f"{'primary-container' if is_active else 'surface-container'} "
                        "small-round"
                    ),
                    aria_current="true" if is_active else None,
                )
            )
        return document(
            "FastPrize | Events",
            Article(
                H1("Choose your event.", cls="small"),
                P("Pick up where the suspense left off, or start a new one."),
                cls="card padding primary-container small-round vertical",
            ),
            Article(
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
                        cls="s12 m7 field label border fill round extra",
                    ),
                    Button(
                        I("add"),
                        Span("Create event"),
                        type="submit",
                        cls="s12 m5 responsive extra primary",
                    ),
                    action="/events",
                    method="post",
                    cls="grid bottom-padding",
                ),
                cls="card padding secondary-container small-round vertical",
            ),
            Article(
                H2("Your events", cls="small"),
                Div(*event_links, cls="grid")
                if event_links
                else P(
                    "No events yet. Create one to start adding entrants and prizes.",
                    cls="secondary-text",
                ),
                cls="card padding secondary-container small-round vertical",
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
        clear_notice = message if status == "data-cleared" else ""
        return document(
            f"FastPrize | {event['name']} | Events",
            Article(
                H1(event["name"], cls="small"),
                cls="card padding primary-container small-round vertical bottom-padding",
            ),
            Div(
                Section(
                    H2("Entrants", cls="small"),
                    Div(
                        Article(
                            H3(str(len(entrants)), cls="extra"),
                            P("total"),
                            cls="s6 card padding tertiary-container small-round",
                        ),
                        Article(
                            H3(str(eligible_count), cls="extra"),
                            P("eligible"),
                            cls="s6 card padding tertiary-container small-round",
                        ),
                        cls="grid",
                    ),
                    cls="s12 m6 card padding secondary-container small-round vertical bottom-padding",
                ),
                Section(
                    H2("Prizes", cls="small"),
                    Div(
                        Article(
                            H3(str(len(prizes)), cls="extra"),
                            P("total"),
                            cls="s6 card padding tertiary-container small-round",
                        ),
                        Article(
                            H3(str(available_count), cls="extra"),
                            P("available"),
                            cls="s6 card padding tertiary-container small-round",
                        ),
                        cls="grid",
                    ),
                    cls="s12 m6 card padding secondary-container small-round vertical bottom-padding",
                ),
                Details(
                    Summary(
                        I("expand_more", data_add_expansion_chevron=True),
                        Span("Import CSV"),
                        cls="button primary responsive none",
                        aria_expanded="false",
                    ),
                    Article(
                        Form(
                            Div(
                                Div(
                                    H3("Entrants", cls="small"),
                                    Button(
                                        I("info"),
                                        type="button",
                                        title="Entrant CSV requirements",
                                        aria_label="Entrant CSV requirements",
                                        aria_haspopup="dialog",
                                        aria_controls="entrants-csv-info",
                                        data_ui="#entrants-csv-info",
                                        cls="circle transparent",
                                    ),
                                    cls="horizontal middle-align small-space bottom-margin",
                                ),
                                Dialog(
                                    H2("Entrants CSV", cls="small"),
                                    P("Required: name. Optional: organization."),
                                    Nav(
                                        Button(
                                            "Close",
                                            type="button",
                                            data_ui="#entrants-csv-info",
                                            cls="text",
                                        ),
                                        cls="right-align",
                                    ),
                                    id="entrants-csv-info",
                                    aria_label="Entrant CSV requirements",
                                    data_close_on_backdrop="true",
                                    cls="modal padding medium-width left-align",
                                ),
                                Label(
                                    I("attach_file"),
                                    Span("Entrants CSV", id="entrants-file-name"),
                                    fr="entrants-file",
                                    cls="button secondary",
                                ),
                                Input(
                                    id="entrants-file",
                                    type="file",
                                    name="entrants_file",
                                    accept=".csv,text/csv",
                                    hidden=True,
                                    data_filename_target="entrants-file-name",
                                ),
                                cls="s12 m6 l6 vertical",
                            ),
                            Div(
                                Div(
                                    H3("Prizes", cls="small"),
                                    Button(
                                        I("info"),
                                        type="button",
                                        title="Prize CSV requirements",
                                        aria_label="Prize CSV requirements",
                                        aria_haspopup="dialog",
                                        aria_controls="prizes-csv-info",
                                        data_ui="#prizes-csv-info",
                                        cls="circle transparent",
                                    ),
                                    cls="horizontal middle-align small-space bottom-margin",
                                ),
                                Dialog(
                                    H2("Prizes CSV", cls="small"),
                                    P(
                                        "Required: prize_name. Optional: sponsor, "
                                        "number (or prize_number)."
                                    ),
                                    Nav(
                                        Button(
                                            "Close",
                                            type="button",
                                            data_ui="#prizes-csv-info",
                                            cls="text",
                                        ),
                                        cls="right-align",
                                    ),
                                    id="prizes-csv-info",
                                    aria_label="Prize CSV requirements",
                                    data_close_on_backdrop="true",
                                    cls="modal padding medium-width left-align",
                                ),
                                Label(
                                    I("attach_file"),
                                    Span("Prizes CSV", id="prizes-file-name"),
                                    fr="prizes-file",
                                    cls="button secondary",
                                ),
                                Input(
                                    id="prizes-file",
                                    type="file",
                                    name="prizes_file",
                                    accept=".csv,text/csv",
                                    hidden=True,
                                    data_filename_target="prizes-file-name",
                                ),
                                cls="s12 m6 l6 vertical",
                            ),
                            Button(
                                I("upload_file"),
                                "Import selected files",
                                type="submit",
                                cls="s12 responsive extra primary",
                            ),
                            action=f"/events/{event_id}/import",
                            method="post",
                            enctype="multipart/form-data",
                            cls="grid small-space",
                        ),
                        cls="card padding secondary-container small-round vertical bottom-padding",
                    ),
                    id="csv-import",
                    data_add_expansion="true",
                    cls="s12 vertical",
                ),
                cls="grid small-space",
            ),
            P(message, cls="tertiary-container padding")
            if message and not clear_notice
            else "",
            Div(
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
                    cls="s12 m6 card padding secondary-container small-round vertical bottom-padding",
                ),
                Section(
                    H2("Data management", cls="small"),
                    P("Remove all entrants and prizes from this event."),
                    Div(
                        Div(
                            Button(
                                I("delete"),
                                Span("Clear Data"),
                                type="button",
                                aria_haspopup="dialog",
                                aria_controls="clear-database-dialog",
                                data_ui="#clear-database-dialog",
                                cls="s12 responsive extra error",
                            ),
                            Dialog(
                                H2("Clear database?", cls="small"),
                                P(
                                    "This removes all entrants and prizes from this event. This cannot be undone."
                                ),
                                Nav(
                                    Button(
                                        "Cancel",
                                        type="button",
                                        data_ui="#clear-database-dialog",
                                        cls="text",
                                    ),
                                    Form(
                                        Button(
                                            I("delete"),
                                            Span("Clear Database"),
                                            type="submit",
                                            cls="error",
                                        ),
                                        action=f"/events/{event_id}/clear-data",
                                        method="post",
                                    ),
                                    cls="horizontal",
                                ),
                                id="clear-database-dialog",
                                aria_label="Confirm clearing event data",
                                cls="modal padding medium-width",
                            ),
                            cls="s12 m6",
                        ),
                        Div(
                            Button(
                                I("delete_forever"),
                                Span("Delete event"),
                                type="button",
                                aria_haspopup="dialog",
                                aria_controls="delete-event-dialog",
                                data_ui="#delete-event-dialog",
                                cls="s12 responsive extra error",
                            ),
                            Dialog(
                                H2("Delete event?", cls="small"),
                                P(
                                    "This permanently deletes the event, its entrants, prizes, and draw history. This cannot be undone."
                                ),
                                Nav(
                                    Button(
                                        "Cancel",
                                        type="button",
                                        data_ui="#delete-event-dialog",
                                        cls="text",
                                    ),
                                    Form(
                                        Button(
                                            I("delete_forever"),
                                            Span("Delete event"),
                                            type="submit",
                                            cls="error",
                                        ),
                                        action=f"/events/{event_id}/delete",
                                        method="post",
                                    ),
                                    cls="horizontal",
                                ),
                                id="delete-event-dialog",
                                aria_label="Confirm deleting this event",
                                cls="modal padding medium-width",
                            ),
                            cls="s12 m6",
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
                    cls="s12 m6 card padding secondary-container small-round vertical",
                ),
                cls="grid small-space",
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

    @rt("/events/{event_id}/delete", methods=["POST"])
    def delete_event(event_id: int):
        store.delete_event(event_id)
        return RedirectResponse("/events", status_code=303)
