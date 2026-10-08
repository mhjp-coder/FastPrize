from fasthtml.common import (
    H1,
    H2,
    Article,
    Button,
    Dialog,
    Div,
    Form,
    HTTPException,
    I,
    Input,
    Label,
    Nav,
    P,
    Request,
    Small,
    Span,
    Strong,
)

from fastprize.ui import document, redirect_event, status_message


def register_routes(rt, store):
    def prize_info(prize):
        return Div(
            Strong(prize["prize_name"]),
            Small(prize["sponsor"] or "No sponsor listed"),
            cls="vertical",
            id=f"prize-info-{prize['id']}",
        )

    def find_prize(event_id, prize_id):
        return next(
            (prize for prize in store.prizes(event_id) if prize["id"] == prize_id),
            None,
        )

    def prize_count_text(event_id):
        prizes = store.prizes(event_id)
        available_count = sum(not prize["drawn"] for prize in prizes)
        return f"{available_count} available | {len(prizes)} total"

    def prize_count_update(event_id):
        return P(
            prize_count_text(event_id),
            id="prize-counts",
            hx_swap_oob="outerHTML",
        )

    def prize_row(event_id, prize, include_count=False, draw=None):
        prize_id = prize["id"]
        if prize["drawn"]:
            return_dialog = f"return-prize-dialog-{prize_id}"
            return_url = f"/events/{event_id}/prizes/{prize_id}/return"
            entrant_name = draw["entrant_name"] if draw else "the winner"
            award_status = Small(f"Awarded to {entrant_name}", cls="tertiary-container")
            actions = [
                Div(
                    Button(
                        I("undo"),
                        type="button",
                        title=f"Return {prize['prize_name']} to the prize pool",
                        aria_label=f"Return {prize['prize_name']} to the prize pool",
                        aria_haspopup="dialog",
                        aria_controls=return_dialog,
                        data_ui=f"#{return_dialog}",
                        cls="circle primary",
                    ),
                    Dialog(
                        H2("Return prize to pool?", cls="small"),
                        P(
                            "Remove the award of ",
                            Strong(prize["prize_name"]),
                            " to ",
                            Strong(entrant_name),
                            " from draw history and make this prize and entrant ",
                            "available to draw again?",
                        ),
                        Nav(
                            Button(
                                "Cancel",
                                type="button",
                                data_ui=f"#{return_dialog}",
                                cls="text",
                            ),
                            Form(
                                Button(
                                    I("undo"),
                                    Span("Return to pool"),
                                    type="submit",
                                    cls="primary",
                                ),
                                action=return_url,
                                method="post",
                                hx_post=return_url,
                                hx_target=f"#prize-row-{prize_id}",
                                hx_swap="outerHTML",
                            ),
                            cls="horizontal",
                        ),
                        id=return_dialog,
                        aria_label=f"Confirm returning {prize['prize_name']} to pool",
                        cls="modal padding medium-width left-align",
                    ),
                ),
            ]
        else:
            award_status = ""
            actions = [
                Button(
                    I("edit"),
                    type="button",
                    title=f"Edit {prize['prize_name']}",
                    aria_label=f"Edit {prize['prize_name']}",
                    cls="button circle primary",
                    hx_get=f"/events/{event_id}/prizes/{prize_id}/edit",
                    hx_target=f"#prize-info-{prize_id}",
                    hx_swap="outerHTML",
                ),
                Div(
                    Button(
                        I("delete"),
                        type="button",
                        title=f"Remove {prize['prize_name']}",
                        aria_label=f"Remove {prize['prize_name']}",
                        aria_haspopup="dialog",
                        aria_controls=f"remove-prize-dialog-{prize_id}",
                        data_ui=f"#remove-prize-dialog-{prize_id}",
                        cls="circle error",
                    ),
                    Dialog(
                        H2("Remove prize?", cls="small"),
                        P(
                            f"Remove {prize['prize_name']} from this event? "
                            "This cannot be undone."
                        ),
                        Nav(
                            Button(
                                "Cancel",
                                type="button",
                                data_ui=f"#remove-prize-dialog-{prize_id}",
                                cls="text",
                            ),
                            Form(
                                Button(
                                    I("delete"),
                                    Span("Remove"),
                                    type="submit",
                                    cls="error",
                                ),
                                action=f"/events/{event_id}/prizes/{prize_id}/remove",
                                method="post",
                                hx_post=f"/events/{event_id}/prizes/{prize_id}/remove",
                                hx_target=f"#prize-row-{prize_id}",
                                hx_swap="delete",
                            ),
                            cls="horizontal",
                        ),
                        id=f"remove-prize-dialog-{prize_id}",
                        aria_label=f"Confirm removing {prize['prize_name']}",
                        cls="modal padding medium-width left-align",
                    ),
                ),
            ]
        return Article(
            prize_info(prize),
            award_status,
            Div(
                Small(f"# {prize['number']}", cls="s6") if prize["number"] else "",
                Div(
                    *actions,
                    cls=(
                        "s6 horizontal middle-align small-space right-align"
                        if prize["number"]
                        else "s12 horizontal middle-align small-space right-align"
                    ),
                ),
                cls="grid middle-align small-space top-margin bottom-margin",
            ),
            prize_count_update(event_id) if include_count else "",
            cls="s12 m6 l6 card padding tertiary-container small-round vertical",
            id=f"prize-row-{prize_id}",
        )

    def prize_list(event_id, prizes, search=""):
        if prizes:
            draws_by_prize = (
                {
                    draw["prize_id"]: draw
                    for draw in store.draw_history(event_id)
                    if draw["prize_id"] is not None
                }
                if any(prize["drawn"] for prize in prizes)
                else {}
            )
            content = [
                prize_row(event_id, prize, draw=draws_by_prize.get(prize["id"]))
                for prize in prizes
            ]
        elif search:
            content = [P("No prizes match your search.", cls="s12 secondary-text")]
        else:
            content = [
                P("No prizes yet.", cls="s12 secondary-text"),
                Form(
                    Button(
                        I("event"),
                        "Manage event",
                        type="submit",
                        cls="responsive extra primary",
                    ),
                    action=f"/events/{event_id}",
                    method="get",
                    cls="s12",
                ),
            ]
        return Div(*content, cls="grid small-space", id="prize-list")

    @rt("/events/{event_id}/prizes", methods=["GET"])
    def prizes_page(event_id: int, status: str = ""):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        prizes = store.prizes(event_id)
        available_count = sum(not prize["drawn"] for prize in prizes)
        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Prizes",
            Article(
                H1("Prizes", cls="small"),
                P(
                    f"{available_count} available | {len(prizes)} total",
                    id="prize-counts",
                ),
                cls="card padding primary-container small-round vertical bottom-margin",
            ),
            P(message, cls="tertiary-container padding") if message else "",
            Article(
                H2("Add prize", cls="small"),
                Form(
                    Div(
                        Input(
                            id="prize-name",
                            name="name",
                            required=True,
                            type="text",
                        ),
                        Label("Prize name", fr="prize-name"),
                        cls="s6 m6 l4 field label border fill round extra",
                    ),
                    Div(
                        Input(
                            id="prize-sponsor",
                            name="sponsor",
                            type="text",
                            aria_label="Sponsor (optional)",
                        ),
                        Label("Sponsor", fr="prize-sponsor"),
                        cls="s6 m6 l4 field label border fill round extra",
                    ),
                    Div(
                        Input(
                            id="prize-number",
                            name="number",
                            type="text",
                            aria_label="Prize number (optional)",
                        ),
                        Label("Prize number", fr="prize-number"),
                        cls="s6 m6 l4 field label border fill round extra",
                    ),
                    Button(
                        I("add"),
                        Span("Add prize"),
                        type="submit",
                        cls="s12 responsive extra primary",
                    ),
                    action=f"/events/{event_id}/prizes",
                    method="post",
                    cls="grid small-space bottom-padding",
                ),
                cls="card padding secondary-container small-round vertical bottom-padding",
            ),
            Article(
                Div(
                    H2("Prize list", cls="s12 m6 small"),
                    Div(
                        I("search", cls="front"),
                        Input(
                            id="prize-search",
                            name="search",
                            type="search",
                            placeholder="Search prizes",
                            aria_label="Search prizes",
                            autocomplete="off",
                            hx_get=f"/events/{event_id}/prizes/search",
                            hx_trigger="input changed delay:300ms",
                            hx_target="#prize-list",
                            hx_swap="outerHTML",
                        ),
                        cls="s12 m6 field large prefix round fill border active",
                    ),
                    cls="grid middle-align",
                ),
                prize_list(event_id, prizes),
                cls="card padding secondary-container small-round vertical bottom-padding",
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="prizes",
        )

    @rt("/events/{event_id}/prizes/search", methods=["GET"])
    def search_prizes(event_id: int, search: str = ""):
        if store.get_event(event_id) is None:
            raise HTTPException(status_code=404)
        query = search.strip().casefold()
        prizes = [
            prize
            for prize in store.prizes(event_id)
            if query in prize["prize_name"].casefold()
            or query in (prize["sponsor"] or "").casefold()
            or query in (prize["number"] or "").casefold()
        ]
        return prize_list(event_id, prizes, search)

    @rt("/events/{event_id}/prizes", methods=["POST"])
    def add_prize(event_id: int, name: str, sponsor: str = "", number: str = ""):
        try:
            store.add_prize(event_id, name, sponsor, number)
        except ValueError:
            return redirect_event(event_id, "invalid-prize", "prizes")
        return redirect_event(event_id, "prize-added", "prizes")

    @rt("/events/{event_id}/prizes/{prize_id}/edit", methods=["GET"])
    def edit_prize_form(event_id: int, prize_id: int):
        prize = find_prize(event_id, prize_id)
        if prize is None or prize["drawn"]:
            raise HTTPException(status_code=404)
        return Form(
            Div(
                Div(
                    Input(
                        name="name",
                        value=prize["prize_name"],
                        required=True,
                        aria_label="Prize name",
                    ),
                    cls="field round fill border",
                ),
                Div(
                    Input(
                        name="sponsor",
                        value=prize["sponsor"],
                        aria_label="Prize sponsor",
                    ),
                    cls="field round fill border",
                ),
                Div(
                    Input(
                        name="number",
                        value=prize["number"],
                        aria_label="Prize number",
                    ),
                    cls="field round fill border",
                ),
                cls="s8 m9 l9 vertical",
            ),
            Div(
                Button(
                    I("save"),
                    type="submit",
                    aria_label="Save prize",
                    title="Save prize",
                    cls="circle primary",
                ),
                Div(cls="small-space"),
                Button(
                    I("close"),
                    type="button",
                    aria_label="Cancel edit",
                    title="Cancel edit",
                    hx_get=f"/events/{event_id}/prizes/{prize_id}/display",
                    hx_target=f"#prize-info-{prize_id}",
                    hx_swap="outerHTML",
                    cls="circle",
                ),
                cls="s4 m3 l3 vertical",
            ),
            action=f"/events/{event_id}/prizes/{prize_id}/edit",
            method="post",
            hx_post=f"/events/{event_id}/prizes/{prize_id}/edit",
            hx_target=f"#prize-row-{prize_id}",
            hx_swap="outerHTML",
            cls="grid middle-align small-space",
            id=f"prize-info-{prize_id}",
        )

    @rt("/events/{event_id}/prizes/{prize_id}/display", methods=["GET"])
    def prize_display(event_id: int, prize_id: int):
        prize = find_prize(event_id, prize_id)
        if prize is None:
            raise HTTPException(status_code=404)
        return prize_info(prize)

    @rt("/events/{event_id}/prizes/{prize_id}/edit", methods=["POST"])
    def edit_prize(
        event_id: int,
        prize_id: int,
        req: Request,
        name: str,
        sponsor: str = "",
        number: str = "",
    ):
        try:
            updated = store.update_prize(event_id, prize_id, name, sponsor, number)
        except ValueError:
            return redirect_event(event_id, "invalid-prize", "prizes")
        if req.headers.get("HX-Request") == "true" and updated:
            return prize_row(event_id, find_prize(event_id, prize_id))
        return redirect_event(
            event_id,
            "prize-updated" if updated else "prize-locked",
            "prizes",
        )

    @rt("/events/{event_id}/prizes/{prize_id}/remove", methods=["POST"])
    def remove_prize(event_id: int, prize_id: int, req: Request):
        removed = store.remove_prize(event_id, prize_id)
        if req.headers.get("HX-Request") == "true" and removed:
            return prize_count_update(event_id)
        return redirect_event(
            event_id,
            "prize-removed" if removed else "prize-locked",
            "prizes",
        )

    @rt("/events/{event_id}/prizes/{prize_id}/return", methods=["POST"])
    def return_awarded_prize(event_id: int, prize_id: int, req: Request):
        returned = store.return_prize_to_pool(event_id, prize_id)
        if req.headers.get("HX-Request") == "true" and returned:
            return prize_row(
                event_id, find_prize(event_id, prize_id), include_count=True
            )
        return redirect_event(
            event_id,
            "prize-returned" if returned else "prize-locked",
            "prizes",
        )
