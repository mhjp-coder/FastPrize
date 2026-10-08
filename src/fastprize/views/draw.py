from fasthtml.common import (
    H1,
    H2,
    A,
    Article,
    Button,
    Div,
    Form,
    HTTPException,
    I,
    Input,
    JSONResponse,
    Nav,
    P,
    RedirectResponse,
    Request,
    Small,
    Span,
    Strong,
)

from fastprize.ui import (
    display_link_modal,
    document,
    draw_preview_modal,
    redirect_event,
    status_message,
    winner_fragment,
)


def register_routes(rt, store):
    def current_result(event_id: int):
        preview = store.latest_preview(event_id)
        draw = store.latest_draw(event_id)
        return (
            preview
            if preview and (draw is None or preview["created_at"] >= draw["created_at"])
            else draw
        )

    def draw_prize_list(event_id: int, prizes, eligible_count: int, search=""):
        if prizes:
            prize_rows = [
                Article(
                    Div(
                        Strong(prize["prize_name"]),
                        Small(prize["sponsor"] or "No sponsor listed"),
                        cls="vertical",
                    ),
                    Div(
                        Small(f"# {prize['number']}", cls="s6")
                        if prize["number"]
                        else "",
                        (
                            Form(
                                Button(
                                    I("casino"),
                                    Span("Draw"),
                                    type="submit",
                                    cls="primary",
                                    disabled=eligible_count == 0,
                                ),
                                action=f"/events/{event_id}/draws/{prize['id']}/preview",
                                method="post",
                                cls=(
                                    "s6 right-align"
                                    if prize["number"]
                                    else "s12 right-align"
                                ),
                            )
                            if not prize["drawn"]
                            else Div(
                                Button("Awarded", type="button", disabled=True),
                                cls=(
                                    "s6 right-align"
                                    if prize["number"]
                                    else "s12 right-align"
                                ),
                            )
                        ),
                        cls="grid middle-align small-space top-margin bottom-margin",
                    ),
                    cls="s12 m6 l6 card padding tertiary-container small-round vertical",
                )
                for prize in prizes
            ]
            return Div(*prize_rows, cls="grid small-space", id="draw-prize-list")
        if search.strip():
            return Div(
                P("No prizes match your search.", cls="s12 secondary-text"),
                cls="grid small-space",
                id="draw-prize-list",
            )
        return Div(
            P("No prizes are available to draw."),
            Form(
                Button(
                    I("event"),
                    "Manage event",
                    type="submit",
                    cls="s12 responsive extra primary",
                ),
                action=f"/events/{event_id}",
                method="get",
            ),
            cls="vertical",
            id="draw-prize-list",
        )

    @rt("/events/{event_id}/draw")
    def draw_page(
        event_id: int,
        status: str = "",
        preview: int | None = None,
        winner: int | None = None,
    ):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        prizes = store.prizes(event_id)
        entrants = store.entrants(event_id)
        available_prizes = [prize for prize in prizes if not prize["drawn"]]
        prize_count = len(available_prizes)
        prize_label = "prize" if prize_count == 1 else "prizes"
        eligible_count = sum(entrant["eligible"] for entrant in entrants)
        preview_modal = None
        if preview is not None and winner is not None:
            prize = next((item for item in prizes if item["id"] == preview), None)
            entrant = next((item for item in entrants if item["id"] == winner), None)
            if prize and entrant:
                preview_modal = draw_preview_modal(
                    event_id,
                    preview,
                    winner,
                    prize,
                    entrant,
                )
        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Draw",
            Article(
                Nav(
                    H1("Live Draw", cls="small max"),
                    Button(
                        I("qr_code_2"),
                        Span("Live display", cls="m l"),
                        type="button",
                        title="Live display",
                        aria_label="Live display",
                        aria_haspopup="dialog",
                        hx_get=f"/events/{event_id}/display-link",
                        hx_target="#display-link-modal",
                        hx_swap="innerHTML",
                        cls="tertiary",
                    ),
                ),
                Div(
                    P(event["name"], cls="s9"),
                    Span(
                        f"{prize_count} {prize_label} left",
                        cls="s3 right-align",
                    ),
                    cls="grid middle-align",
                ),
                cls="card padding primary-container small-round vertical bottom-margin",
            ),
            P(message, cls="tertiary-container padding") if message else "",
            preview_modal if preview_modal else "",
            Article(
                Div(
                    H2("Prizes", cls="s12 m6 small"),
                    Div(
                        I("search", cls="front"),
                        Input(
                            id="draw-prize-search",
                            name="search",
                            type="search",
                            placeholder="Search prizes",
                            aria_label="Search prizes",
                            autocomplete="off",
                            hx_get=f"/events/{event_id}/draw/search",
                            hx_trigger="input changed delay:300ms",
                            hx_target="#draw-prize-list",
                            hx_swap="outerHTML",
                        ),
                        cls="s12 m6 field large prefix round fill border active",
                    ),
                    cls="grid middle-align",
                ),
                draw_prize_list(event_id, prizes, eligible_count),
                cls="card padding secondary-container small-round vertical bottom-padding",
            ),
            Div(
                P(
                    "Add an eligible entrant before starting a draw.",
                    cls="secondary-container padding",
                ),
                A(
                    I("groups"),
                    "Manage entrants",
                    href=f"/events/{event_id}/entrants",
                    cls="secondary",
                ),
                cls="vertical",
            )
            if eligible_count == 0 and available_prizes
            else "",
            event_id=event_id,
            event_name=event["name"],
            active_link="draw",
        )

    @rt("/events/{event_id}/draw/search", methods=["GET"])
    def search_draw_prizes(event_id: int, search: str = ""):
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
        eligible_count = sum(
            entrant["eligible"] for entrant in store.entrants(event_id)
        )
        return draw_prize_list(event_id, prizes, eligible_count, search)

    def preview_draw_prize(event_id: int, prize_id: int):
        try:
            preview = store.preview_draw(event_id, prize_id)
            store.save_preview(event_id, prize_id, preview["winner"], preview["prize"])
        except ValueError:
            return redirect_event(event_id, "no-eligible-entrants", "draw")
        return RedirectResponse(
            f"/events/{event_id}/draw?preview={prize_id}&winner={preview['winner']['id']}",
            status_code=303,
        )

    @rt("/events/{event_id}/draws/{prize_id}/preview", methods=["POST"])
    def preview_draw(event_id: int, prize_id: int):
        return preview_draw_prize(event_id, prize_id)

    @rt("/events/{event_id}/draws/{prize_id}/award", methods=["POST"])
    def award_draw_prize(event_id: int, prize_id: int, winner: int):
        try:
            winner_entry = next(
                entrant
                for entrant in store.entrants(event_id)
                if entrant["id"] == winner
            )
            store.draw(
                event_id,
                prize_id,
                chooser=lambda entrants: next(
                    entrant
                    for entrant in entrants
                    if entrant["id"] == winner_entry["id"]
                ),
            )
        except ValueError, StopIteration:
            return redirect_event(event_id, "no-eligible-entrants", "draw")
        return redirect_event(event_id, "draw-complete", "draw")

    @rt("/events/{event_id}/draws/{prize_id}", methods=["POST"])
    def draw_prize(event_id: int, prize_id: int):
        return preview_draw_prize(event_id, prize_id)

    @rt("/events/{event_id}/display-link")
    def display_link(req: Request, event_id: int):
        if store.get_event(event_id) is None:
            raise HTTPException(status_code=404)
        base_url = str(req.base_url).rstrip("/")
        return display_link_modal(f"{base_url}/events/{event_id}/display")

    @rt("/events/{event_id}/display")
    def display(event_id: int):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        return document(
            f"{event['name']} | Live draw",
            Div(
                Div("LIVE PRIZE DRAW", cls="upper small-text secondary-text"),
                winner_fragment(
                    current_result(event_id),
                    poll_url=f"/events/{event_id}/display/latest-fragment",
                ),
                cls="responsive center-align",
            ),
            P("FastPrize | Live draw", cls="small-text"),
            screen=True,
        )

    @rt("/events/{event_id}/display/latest-fragment")
    def latest_display_fragment(event_id: int):
        if store.get_event(event_id) is None:
            raise HTTPException(status_code=404)
        return winner_fragment(
            current_result(event_id),
            poll_url=f"/events/{event_id}/display/latest-fragment",
        )

    @rt("/events/{event_id}/display/latest")
    def latest_display_result(event_id: int):
        if store.get_event(event_id) is None:
            raise HTTPException(status_code=404)
        return JSONResponse(current_result(event_id) or {})
