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
    Strong,
    Summary,
)

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
                [Small("Awarded", cls="tertiary-container")]
                if prize["drawn"]
                else [
                    Form(
                        Button(I("casino"), "Draw", type="submit", cls="primary"),
                        action=f"/events/{event_id}/draws/{prize['id']}",
                        method="post",
                    ),
                    Form(
                        Button(I("delete"), "Remove", type="submit", cls="error"),
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
                                cls="s12 m5 l5",
                            ),
                            Input(
                                name="sponsor",
                                value=prize["sponsor"],
                                aria_label="Prize sponsor",
                                cls="s12 m5 l5",
                            ),
                            Button("Save", type="submit", cls="s12 m2 l2 primary"),
                            action=f"/events/{event_id}/prizes/{prize['id']}/edit",
                            method="post",
                            cls="grid",
                        ),
                    )
                ]
            )
            return Li(
                Div(
                    Strong(prize["prize_name"]),
                    Small(prize["sponsor"] or "No sponsor listed"),
                    cls="vertical",
                ),
                Div(*actions, cls="horizontal"),
                *edit_form,
            )

        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Prizes",
            Div(
                Div("AWARDS", cls="upper small-text secondary-text"),
                H1("Prizes", cls="small"),
                P(f"{available_count} available | {len(prizes)} total"),
                cls="vertical",
            ),
            P(message, cls="tertiary-container padding") if message else "",
            Section(
                H2("Add prize", cls="small"),
                Form(
                    Input(
                        name="name",
                        placeholder="Prize name",
                        required=True,
                        cls="s12 m5 l5",
                    ),
                    Input(
                        name="sponsor",
                        placeholder="Sponsor (optional)",
                        cls="s12 m5 l5",
                    ),
                    Button(
                        I("add"),
                        "Add prize",
                        type="submit",
                        cls="s12 m2 l2 primary large",
                    ),
                    action=f"/events/{event_id}/prizes",
                    method="post",
                    cls="grid",
                ),
                cls="vertical",
            ),
            Section(
                H2("Prize list", cls="small"),
                record_list(prizes, "No prizes yet.", prize_row),
                cls="vertical",
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
