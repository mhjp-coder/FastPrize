from fasthtml.common import (
    Div,
    Form,
    HTTPException,
    Label,
    Li,
    Span,
    Strong,
)
from monsterui.franken import Button as ThemeButton
from monsterui.franken import (
    ButtonT,
    Card,
    FlexT,
    Grid,
    Input,
    Small,
    Switch,
    TextT,
    UkIcon,
)

from fastprize.ui import (
    document,
    emphasized,
    hstack,
    page_header,
    record_actions,
    record_body,
    record_list,
    record_row,
    redirect_event,
    search_field,
    stat_card,
    status_banner,
    status_message,
    status_tone,
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
                record_row(
                    record_body(
                        Strong(entrant["name"], data_read="1"),
                        Small(
                            entrant["organization"] or "No organization listed",
                            data_read="1",
                            cls=TextT.meta,
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
                            hstack(
                                ThemeButton("Save", cls=ButtonT.primary),
                                ThemeButton(
                                    "Cancel",
                                    type="button",
                                    onclick="cancelEdit(this)",
                                    cls=ButtonT.secondary,
                                ),
                            ),
                            action=f"/events/{event_id}/entrants/{entrant['id']}/edit",
                            method="post",
                            hidden=True,
                            data_write="1",
                            cls=(FlexT.block, FlexT.column, "record-edit w-full gap-3"),
                        ),
                    ),
                    record_actions(
                        Label(
                            Switch(
                                checked=bool(entrant["eligible"]) or None,
                                aria_label=f"Eligible status for {entrant['name']}",
                                data_confirm=(
                                    f"Mark {emphasized(entrant['name'])} "
                                    + (
                                        "ineligible for future draws?"
                                        if entrant["eligible"]
                                        else "eligible for future draws?"
                                    )
                                ),
                                data_confirm_action=(
                                    f"/events/{event_id}/entrants/{entrant['id']}/eligible"
                                ),
                                data_confirm_label="Update",
                                data_confirm_title="Confirm eligibility",
                                data_confirm_field="eligible",
                                data_confirm_value="0" if entrant["eligible"] else "1",
                                onchange="this.checked = !this.checked; confirmDelete(this)",
                            ),
                            Span("Eligible"),
                            cls=(
                                FlexT.inline,
                                FlexT.middle,
                                "w-fit cursor-pointer gap-3",
                            ),
                        ),
                        ThemeButton(
                            UkIcon("pencil"),
                            type="button",
                            onclick="startEdit(this)",
                            data_read="1",
                            cls=(ButtonT.secondary, ButtonT.icon, "icon-btn"),
                            aria_label="Edit",
                        ),
                        ThemeButton(
                            UkIcon("trash-2"),
                            type="button",
                            cls=(ButtonT.destructive, ButtonT.icon, "icon-btn"),
                            aria_label="Remove",
                            data_confirm=(
                                f"Remove {emphasized(entrant['name'])}"
                                + (
                                    f" ({emphasized(entrant['organization'])})"
                                    if entrant["organization"]
                                    else ""
                                )
                                + " from this event?"
                            ),
                            data_confirm_action=f"/events/{event_id}/entrants/{entrant['id']}/remove",
                            onclick="confirmDelete(this)",
                        ),
                    ),
                ),
                data_search=f"{entrant['name']} {entrant['organization'] or ''}".lower(),
            )

        return document(
            f"FastPrize | {event['name']} | Entrants",
            page_header("Entrants"),
            status_banner(status_message(status), status_tone(status)),
            Grid(
                stat_card(eligible_count, "eligible"),
                stat_card(len(entrants), "total"),
                cols_max=2,
                cls="gap-6",
            ),
            Card(
                Form(
                    Input(
                        name="name",
                        placeholder="Full name",
                        required=True,
                        aria_label="Entrant name",
                    ),
                    Input(
                        name="organization",
                        placeholder="Organization (optional)",
                        aria_label="Organization",
                    ),
                    ThemeButton(
                        UkIcon("plus"),
                        cls=(ButtonT.primary, ButtonT.icon, "icon-btn"),
                        aria_label="Add entrant",
                    ),
                    action=f"/events/{event_id}/entrants",
                    method="post",
                    cls=(
                        "grid grid-cols-1 items-end gap-3 "
                        "md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
                    ),
                ),
            ),
            Card(
                Div(
                    search_field("entrant-list", "Search entrants"),
                    cls="list-search",
                ),
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

    @rt("/events/{event_id}/entrants/{entrant_id}/eligible", methods=["POST"])
    def set_entrant_eligible(event_id: int, entrant_id: int, eligible: int):
        updated = store.set_entrant_eligible(event_id, entrant_id, bool(eligible))
        return redirect_event(
            event_id,
            "entrant-eligibility" if updated else "invalid-entrant",
            "entrants",
        )

    @rt("/events/{event_id}/entrants/{entrant_id}/remove", methods=["POST"])
    def remove_entrant(event_id: int, entrant_id: int):
        store.remove_entrant(event_id, entrant_id)
        return redirect_event(event_id, "entrant-removed", "entrants")
