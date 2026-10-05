from fasthtml.common import (
    H1,
    H2,
    Button,
    Details,
    Div,
    Form,
    Input,
    P,
    Section,
    Small,
    Span,
    Strong,
    Summary,
)
from starlette.exceptions import HTTPException

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
            return Div(
                Div(
                    Strong(entrant["name"]),
                    Small(entrant["organization"] or "No organization listed"),
                    class_="record-info",
                ),
                Div(
                    Span(
                        "Eligible" if entrant["eligible"] else "Winner", class_="badge"
                    ),
                    Form(
                        Button("Remove", type="submit", class_="danger"),
                        action=f"/events/{event_id}/entrants/{entrant['id']}/remove",
                        method="post",
                    ),
                    class_="record-actions",
                ),
                Details(
                    Summary("Edit"),
                    Form(
                        Input(
                            name="name",
                            value=entrant["name"],
                            required=True,
                            aria_label="Entrant name",
                        ),
                        Input(
                            name="organization",
                            value=entrant["organization"],
                            aria_label="Organization",
                        ),
                        Button("Save", type="submit", class_="secondary"),
                        action=f"/events/{event_id}/entrants/{entrant['id']}/edit",
                        method="post",
                        class_="edit-form",
                    ),
                ),
                class_="record",
            )

        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Entrants",
            Div(
                Div("EVENT ROSTER", class_="eyebrow"),
                H1("Entrants"),
                P(f"{len(entrants)} total | {eligible_count} eligible"),
                class_="page-intro",
            ),
            P(message, class_="notice") if message else "",
            Section(
                Form(
                    Input(name="name", placeholder="Full name", required=True),
                    Input(name="organization", placeholder="Organization (optional)"),
                    Button("Add entrant", type="submit"),
                    action=f"/events/{event_id}/entrants",
                    method="post",
                    class_="entry-form",
                ),
                record_list(entrants, "No entrants yet.", entrant_row),
                class_="section",
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
