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
from monsterui.franken import Button, ButtonT, Card, Input, Label, LabelT, UkIcon

from fastprize.store import InvalidPrizeNumber
from fastprize.ui import (
    document,
    emphasized,
    page_header,
    record_list,
    redirect_event,
    search_field,
    stat_card,
    status_banner,
    status_message,
    status_tone,
)


def _prize_label(prize: dict) -> str:
    number = prize.get("prize_number")
    prefix = (
        f"{emphasized('#' + str(number))} " if number is not None else ""
    )
    return prefix + emphasized(prize["prize_name"])


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
        draws = {
            draw["prize_id"]: draw for draw in reversed(store.draw_history(event_id))
        }
        available_count = sum(not prize["drawn"] for prize in prizes)

        def prize_row(prize):
            award = draws.get(prize["id"])
            actions = (
                [
                    Label("Awarded", cls=LabelT.secondary),
                    Button(
                        UkIcon("undo-2"),
                        type="button",
                        cls=(ButtonT.secondary, ButtonT.icon, "icon-btn"),
                        aria_label="Undo award",
                        data_confirm=(
                            "Undo the award of "
                            + _prize_label(prize)
                            + (
                                f" to {emphasized(award['entrant_name'])}"
                                if award
                                else ""
                            )
                            + "? "
                            + (
                                f"{emphasized(award['entrant_name'])} will be eligible again, and this result will leave the history."
                                if award
                                else "The prize will be available again, and its result will leave the history."
                            )
                        ),
                        data_confirm_action=(
                            f"/events/{event_id}/prizes/{prize['id']}/undo"
                        ),
                        data_confirm_label="Undo award",
                        data_confirm_title="Undo award",
                        onclick="confirmDelete(this)",
                    ),
                ]
                if prize["drawn"]
                else [
                    Button(
                        UkIcon("trash-2"),
                        type="button",
                        cls=(ButtonT.destructive, ButtonT.icon, "icon-btn"),
                        aria_label="Remove",
                        data_confirm=(
                            "Remove "
                            + _prize_label(prize)
                            + (
                                f", sponsored by {emphasized(prize['sponsor'])},"
                                if prize["sponsor"]
                                else ""
                            )
                            + " from this event?"
                        ),
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
                        UkIcon("pencil"),
                        type="button",
                        onclick="startEdit(this)",
                        data_read="1",
                        cls=(ButtonT.secondary, ButtonT.icon, "icon-btn"),
                        aria_label="Edit",
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
            page_header("Prizes"),
            status_banner(status_message(status), status_tone(status)),
            Section(
                stat_card(available_count, "available"),
                stat_card(len(prizes), "total"),
                cls="stat-row",
            ),
            Card(
                Form(
                    Input(
                        name="name",
                        placeholder="Prize name",
                        required=True,
                        aria_label="Prize name",
                    ),
                    Input(
                        name="prize_number",
                        placeholder="#",
                        aria_label="Prize number",
                        inputmode="numeric",
                    ),
                    Input(
                        name="sponsor",
                        placeholder="Sponsor (optional)",
                        aria_label="Sponsor",
                    ),
                    Button(
                        UkIcon("plus"),
                        cls=(ButtonT.primary, ButtonT.icon, "icon-btn"),
                        aria_label="Add prize",
                    ),
                    action=f"/events/{event_id}/prizes",
                    method="post",
                    cls="add-prize-form",
                ),
                body_cls="add-card",
            ),
            Card(
                Div(
                    search_field("prize-roster", "Search prizes"),
                    cls="list-search",
                ),
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

    @rt("/events/{event_id}/prizes/{prize_id}/undo", methods=["POST"])
    def undo_award(event_id: int, prize_id: int):
        undone = store.undo_award(event_id, prize_id)
        return redirect_event(
            event_id,
            "award-undone" if undone else "award-missing",
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
