from fasthtml.common import (
    Div,
    Form,
    HTTPException,
    Li,
    Section,
    Small,
    Span,
    Strong,
)
from monsterui.franken import Button as ThemeButton
from monsterui.franken import ButtonT, Card, Input

from fastprize.ui import (
    document,
    page_header,
    record_list,
    redirect_event,
    search_field,
    stat_card,
    status_banner,
    status_message,
)


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
                    Div(
                        Strong(entrant["name"], data_read="1"),
                        Small(
                            entrant["organization"] or "No organization listed",
                            data_read="1",
                        ),
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
                            Div(
                                ThemeButton("Save", cls=ButtonT.primary),
                                ThemeButton(
                                    "Cancel",
                                    type="button",
                                    onclick="cancelEdit(this)",
                                    cls=ButtonT.secondary,
                                ),
                                cls="cluster",
                            ),
                            action=f"/events/{event_id}/entrants/{entrant['id']}/edit",
                            method="post",
                            hidden=True,
                            data_write="1",
                            cls="record-edit",
                        ),
                        cls="record-main",
                    ),
                    Div(
                        Span("Eligible" if entrant["eligible"] else "Winner"),
                        ThemeButton(
                            "Remove",
                            type="button",
                            cls=ButtonT.destructive,
                            data_confirm=f"Remove {entrant['name']} from this event?",
                            data_confirm_action=f"/events/{event_id}/entrants/{entrant['id']}/remove",
                            onclick="confirmDelete(this)",
                        ),
                        ThemeButton(
                            "Edit",
                            type="button",
                            onclick="startEdit(this)",
                            data_read="1",
                            cls=ButtonT.secondary,
                        ),
                        cls="record-actions",
                    ),
                    cls="record",
                ),
                data_search=f"{entrant['name']} {entrant['organization'] or ''}".lower(),
            )

        return document(
            f"FastPrize | {event['name']} | Entrants",
            page_header("Event roster", "Entrants"),
            status_banner(status_message(status)),
            Section(
                stat_card(len(entrants), "total"),
                stat_card(eligible_count, "eligible"),
                Card(
                    Form(
                        Input(name="name", placeholder="Full name", required=True),
                        Input(
                            name="organization",
                            placeholder="Organization (optional)",
                        ),
                        ThemeButton("Add entrant", cls=ButtonT.primary),
                        action=f"/events/{event_id}/entrants",
                        method="post",
                        cls="add-entrant-form",
                    ),
                    body_cls="add-card",
                ),
                cls="stat-row roster-row",
            ),
            Card(
                search_field("entrant-list", "Search entrants"),
                record_list(entrants, "No entrants yet.", entrant_row, list_id="entrant-list"),
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
