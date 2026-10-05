from fasthtml.common import (
    H1,
    Button,
    Details,
    Div,
    Form,
    Input,
    P,
    Section,
    Small,
    Strong,
    Summary,
)
from starlette.exceptions import HTTPException

from fastprize.ui import document, record_list, redirect_event, status_message


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
                [Small("Awarded", class_="badge awarded")]
                if prize["drawn"]
                else [
                    Form(
                        Button("Draw", type="submit"),
                        action=f"/events/{event_id}/draws/{prize['id']}",
                        method="post",
                    ),
                    Form(
                        Button("Remove", type="submit", class_="danger"),
                        action=f"/events/{event_id}/prizes/{prize['id']}/remove",
                        method="post",
                    ),
                ]
            )
            edit_form = (
                []
                if prize["drawn"]
                else [
                    Details(
                        Summary("Edit"),
                        Form(
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
                            Button("Save", type="submit", class_="secondary"),
                            action=f"/events/{event_id}/prizes/{prize['id']}/edit",
                            method="post",
                            class_="edit-form",
                        ),
                    )
                ]
            )
            return Div(
                Div(
                    Strong(prize["prize_name"]),
                    Small(prize["sponsor"] or "No sponsor listed"),
                    class_="record-info",
                ),
                Div(*actions, class_="record-actions"),
                *edit_form,
                class_="record",
            )

        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Prizes",
            Div(
                Div("AWARDS", class_="eyebrow"),
                H1("Prizes"),
                P(f"{available_count} available | {len(prizes)} total"),
                class_="page-intro",
            ),
            P(message, class_="notice") if message else "",
            Section(
                Form(
                    Input(name="name", placeholder="Prize name", required=True),
                    Input(name="sponsor", placeholder="Sponsor (optional)"),
                    Button("Add prize", type="submit"),
                    action=f"/events/{event_id}/prizes",
                    method="post",
                    class_="entry-form",
                ),
                record_list(prizes, "No prizes yet.", prize_row),
                class_="section",
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="prizes",
        )

    @rt("/events/{event_id}/prizes", methods=["POST"])
    def add_prize(event_id: int, name: str, sponsor: str = ""):
        try:
            store.add_prize(event_id, name, sponsor)
        except ValueError:
            return redirect_event(event_id, "invalid-prize", "prizes")
        return redirect_event(event_id, "prize-added", "prizes")

    @rt("/events/{event_id}/prizes/{prize_id}/edit", methods=["POST"])
    def edit_prize(event_id: int, prize_id: int, name: str, sponsor: str = ""):
        try:
            updated = store.update_prize(event_id, prize_id, name, sponsor)
        except ValueError:
            return redirect_event(event_id, "invalid-prize", "prizes")
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
