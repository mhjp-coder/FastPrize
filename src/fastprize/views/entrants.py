from fasthtml.common import (
    H1,
    H2,
    Button,
    Details,
    Div,
    Form,
    HTTPException,
    I,
    Input,
    Li,
    P,
    Section,
    Small,
    Span,
    Strong,
    Summary,
)

from fastprize.ui import document, record_list, redirect_event, status_message


def register_routes(rt, store):
    @rt("/events/{event_id}/entrants", methods=["GET"])
    def entrants_page(event_id: int, status: str = ""):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        entrants = store.entrants(event_id)
        eligible_count = sum(entrant["eligible"] for entrant in entrants)

        def entrant_row(entrant):
            return Li(
                Div(
                    Strong(entrant["name"]),
                    Small(entrant["organization"] or "No organization listed"),
                    cls="vertical",
                ),
                Div(
                    Span(
                        "Eligible" if entrant["eligible"] else "Winner",
                        cls="secondary-container",
                    ),
                    Form(
                        Button(I("delete"), "Remove", type="submit", cls="error"),
                        action=f"/events/{event_id}/entrants/{entrant['id']}/remove",
                        method="post",
                    ),
                    cls="horizontal",
                ),
                Details(
                    Summary("Edit"),
                    Form(
                        Input(
                            name="name",
                            value=entrant["name"],
                            required=True,
                            aria_label="Entrant name",
                            cls="s12 m5 l5",
                        ),
                        Input(
                            name="organization",
                            value=entrant["organization"],
                            aria_label="Organization",
                            cls="s12 m5 l5",
                        ),
                        Button("Save", type="submit", cls="s12 m2 l2 primary"),
                        action=f"/events/{event_id}/entrants/{entrant['id']}/edit",
                        method="post",
                        cls="grid",
                    ),
                ),
            )

        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Entrants",
            Div(
                Div("EVENT ROSTER", cls="upper small-text secondary-text"),
                H1("Entrants", cls="small"),
                P(f"{len(entrants)} total | {eligible_count} eligible"),
                cls="vertical",
            ),
            P(message, cls="tertiary-container padding") if message else "",
            Section(
                H2("Add entrant", cls="small"),
                Form(
                    Input(
                        name="name",
                        placeholder="Full name",
                        required=True,
                        cls="s12 m5 l5",
                    ),
                    Input(
                        name="organization",
                        placeholder="Organization (optional)",
                        cls="s12 m5 l5",
                    ),
                    Button(
                        I("person_add"),
                        "Add entrant",
                        type="submit",
                        cls="s12 m2 l2 primary large",
                    ),
                    action=f"/events/{event_id}/entrants",
                    method="post",
                    cls="grid",
                ),
                cls="vertical",
            ),
            Section(
                H2("Entrant list", cls="small"),
                record_list(entrants, "No entrants yet.", entrant_row),
                cls="vertical",
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="entrants",
        )

    @rt("/events/{event_id}/entrants", methods=["POST"])
    def add_entrant(event_id: int, name: str, organization: str = ""):
        try:
            added = store.add_entrant(event_id, name, organization)
        except ValueError:
            return redirect_event(event_id, "invalid-entrant", "entrants")
        return redirect_event(
            event_id,
            "entrant-added" if added else "invalid-entrant",
            "entrants",
        )

    @rt("/events/{event_id}/entrants/{entrant_id}/edit", methods=["POST"])
    def edit_entrant(event_id: int, entrant_id: int, name: str, organization: str = ""):
        try:
            updated = store.update_entrant(event_id, entrant_id, name, organization)
        except ValueError:
            return redirect_event(event_id, "invalid-entrant", "entrants")
        return redirect_event(
            event_id,
            "entrant-updated" if updated else "invalid-entrant",
            "entrants",
        )

    @rt("/events/{event_id}/entrants/{entrant_id}/remove", methods=["POST"])
    def remove_entrant(event_id: int, entrant_id: int):
        store.remove_entrant(event_id, entrant_id)
        return redirect_event(event_id, "entrant-removed", "entrants")
