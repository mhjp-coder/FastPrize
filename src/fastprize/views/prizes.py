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
from monsterui.franken import Button, ButtonT, Card, Input

from fastprize.store import InvalidPrizeNumber
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


def _prize_title(prize: dict):
    name = Strong(prize["prize_name"])
    number = prize.get("prize_number")
    if number is None:
        return name
    return Div(Span(f"#{number}", cls="prize-number"), name, cls="prize-title")


def register_routes(rt, store):
    @rt("/events/{event_id}/prizes", methods=["GET"])
    def prizes_page(event_id: int, status: str = ""):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        prizes = store.prizes(event_id)
        available_count = sum(not prize["drawn"] for prize in prizes)

        def prize_row(prize):
            actions = (
                [Small("Awarded")]
                if prize["drawn"]
                else [
                    Form(
                        Button("Draw"),
                        action=f"/events/{event_id}/draws/{prize['id']}",
                        method="post",
                    ),
                    Button(
                        "Remove",
                        type="button",
                        cls=ButtonT.destructive,
                        data_confirm=f"Remove {prize['prize_name']} from this event?",
                        data_confirm_action=f"/events/{event_id}/prizes/{prize['id']}/remove",
                        onclick="confirmDelete(this)",
                    ),
                ]
            )
            edit_fields = (
                []
                if prize["drawn"]
                else [
                    Form(
                        Input(
                            name="prize_number",
                            value=""
                            if prize.get("prize_number") is None
                            else str(prize["prize_number"]),
                            aria_label="Prize number",
                            placeholder="#",
                            inputmode="numeric",
                        ),
                        Input(
                            name="name",
                            value=prize["prize_name"],
                            required=True,
                            aria_label="Prize name",
                        ),
                        Input(
                            name="sponsor",
                            value=prize["sponsor"],
                            aria_label="Prize sponsor",
                        ),
                        Div(
                            Button("Save", cls=ButtonT.primary),
                            Button(
                                "Cancel",
                                type="button",
                                onclick="cancelEdit(this)",
                                cls=ButtonT.secondary,
                            ),
                            cls="cluster",
                        ),
                        action=f"/events/{event_id}/prizes/{prize['id']}/edit",
                        method="post",
                        hidden=True,
                        data_write="1",
                        cls="record-edit prize-edit",
                    )
                ]
            )
            edit_button = (
                []
                if prize["drawn"]
                else [
                    Button(
                        "Edit",
                        type="button",
                        onclick="startEdit(this)",
                        data_read="1",
                        cls=ButtonT.secondary,
                    )
                ]
            )
            number = prize.get("prize_number")
            return Li(
                Div(
                    Div(
                        Div(_prize_title(prize), data_read="1"),
                        Small(
                            prize["sponsor"] or "No sponsor listed",
                            data_read="1",
                        ),
                        *edit_fields,
                        cls="record-main",
                    ),
                    Div(*actions, *edit_button, cls="record-actions"),
                    cls="record",
                ),
                data_search=" ".join(
                    part
                    for part in (
                        f"#{number}" if number is not None else "",
                        prize["prize_name"],
                        prize["sponsor"] or "",
                    )
                    if part
                ).lower(),
            )

        return document(
            f"FastPrize | {event['name']} | Prizes",
            page_header("Awards", "Prizes"),
            status_banner(status_message(status)),
            Section(
                stat_card(available_count, "available"),
                stat_card(len(prizes), "total"),
                Card(
                    Form(
                        Input(
                            name="prize_number",
                            placeholder="#",
                            aria_label="Prize number",
                            inputmode="numeric",
                        ),
                        Input(name="name", placeholder="Prize name", required=True),
                        Input(name="sponsor", placeholder="Sponsor (optional)"),
                        Button("Add prize", cls=ButtonT.primary),
                        action=f"/events/{event_id}/prizes",
                        method="post",
                        cls="add-prize-form",
                    ),
                    body_cls="add-card",
                ),
                cls="stat-row roster-row",
            ),
            Card(
                search_field("prize-roster", "Search prizes"),
                record_list(prizes, "No prizes yet.", prize_row, list_id="prize-roster"),
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="prizes",
        )

    def _prize_error(error: Exception) -> str:
        if isinstance(error, InvalidPrizeNumber):
            return "invalid-prize-number"
        return "invalid-prize"

    @rt("/events/{event_id}/prizes", methods=["POST"])
    def add_prize(event_id: int, name: str, sponsor: str = "", prize_number: str = ""):
        try:
            store.add_prize(event_id, name, sponsor, prize_number)
        except (InvalidPrizeNumber, ValueError) as error:
            return redirect_event(event_id, _prize_error(error), "prizes")
        return redirect_event(event_id, "prize-added", "prizes")

    @rt("/events/{event_id}/prizes/{prize_id}/edit", methods=["POST"])
    def edit_prize(
        event_id: int,
        prize_id: int,
        name: str,
        sponsor: str = "",
        prize_number: str = "",
    ):
        try:
            updated = store.update_prize(
                event_id, prize_id, name, sponsor, prize_number
            )
        except (InvalidPrizeNumber, ValueError) as error:
            return redirect_event(event_id, _prize_error(error), "prizes")
        return redirect_event(
            event_id,
            "prize-updated" if updated else "prize-locked",
            "prizes",
        )

    @rt("/events/{event_id}/prizes/{prize_id}/remove", methods=["POST"])
    def remove_prize(event_id: int, prize_id: int):
        removed = store.remove_prize(event_id, prize_id)
        return redirect_event(
            event_id,
            "prize-removed" if removed else "prize-locked",
            "prizes",
        )
