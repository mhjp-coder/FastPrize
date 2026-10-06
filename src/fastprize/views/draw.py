from fasthtml.common import (
    H1,
    H2,
    A,
    Button,
    Div,
    Form,
    HTTPException,
    I,
    JSONResponse,
    Li,
    P,
    RedirectResponse,
    Script,
    Section,
    Small,
    Strong,
    Ul,
)

from fastprize.ui import (
    document,
    draw_preview_modal,
    redirect_event,
    status_message,
    winner_fragment,
)

POLL_SCRIPT = """
let current = document.getElementById('live-result');
function resultNode(draw) {
    const node = document.createElement('div');
    node.id = 'live-result';
    node.dataset.drawId = draw.id ? String(draw.id) : '';
    node.dataset.resultVersion = draw.created_at || '';
    if (!draw.id) {
        const idle = document.createElement('h1');
        idle.className = 'center-align';
        idle.textContent = 'The next name could be yours.';
        node.append(idle);
        return node;
    }
    const eyebrow = document.createElement('div');
    eyebrow.className = 'upper small-text tertiary-text center-align';
    eyebrow.textContent = 'The winner is';
    const name = document.createElement('h1');
    name.textContent = draw.entrant_name;
    const organization = document.createElement('p');
    organization.className = 'medium-text center-align';
    organization.textContent = draw.organization || '';
    const award = document.createElement('div');
    award.className = 'horizontal center-align';
    const prize = document.createElement('strong');
    prize.textContent = draw.prize_name;
    const from = document.createElement('span');
    from.textContent = 'from';
    const sponsor = document.createElement('strong');
    sponsor.textContent = draw.sponsor || 'our conference sponsors';
    award.append(prize, from, sponsor);
    node.append(eyebrow, name, organization, award);
    return node;
}
async function refreshResult() {
  try {
    const response = await fetch(location.pathname + '/latest', {cache: 'no-store'});
    if (!response.ok) return;
    const draw = await response.json();
    const next = resultNode(draw);
    if (next.dataset.resultVersion !== current.dataset.resultVersion) {
      current.replaceWith(next);
      current = next;
    }
  } catch (_) {}
}
setInterval(refreshResult, 1000);
"""


def register_routes(rt, store):
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
        prize_rows = [
            Li(
                Div(
                    Strong(prize["prize_name"]),
                    Small(prize["sponsor"] or "No sponsor listed"),
                    cls="vertical",
                ),
                Form(
                    Button(
                        I("casino"),
                        "Select winner",
                        type="submit",
                        cls="primary large",
                        disabled=eligible_count == 0,
                    ),
                    action=f"/events/{event_id}/draws/{prize['id']}/preview",
                    method="post",
                ),
            )
            for prize in available_prizes
        ]
        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Draw",
            Div(
                Div("LIVE DRAW", cls="upper small-text secondary-text"),
                H1("Draw a prize", cls="small"),
                P(f"{eligible_count} eligible entrants"),
                cls="vertical",
            ),
            P(message, cls="tertiary-container padding") if message else "",
            preview_modal if preview_modal else "",
            Section(
                H2("Available prizes", cls="small"),
                Ul(*prize_rows, cls="border no-space")
                if prize_rows
                else Div(
                    P("No prizes are available to draw."),
                    A(
                        I("add"),
                        "Add a prize",
                        href=f"/events/{event_id}/prizes",
                        cls="secondary",
                    ),
                    cls="vertical",
                ),
                cls="vertical",
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
            A(
                I("present_to_all"),
                "Open projector display",
                href=f"/events/{event_id}/display",
                cls="tertiary large",
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="draw",
        )

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

    @rt("/events/{event_id}/display")
    def display(event_id: int):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        preview = store.latest_preview(event_id)
        draw = store.latest_draw(event_id)
        current_result = (
            preview
            if preview and (draw is None or preview["created_at"] >= draw["created_at"])
            else draw
        )
        return document(
            f"{event['name']} | Live draw",
            Div(
                Div("LIVE PRIZE DRAW", cls="upper small-text secondary-text"),
                winner_fragment(current_result),
                cls="responsive center-align",
            ),
            P("FastPrize | Live draw", cls="small-text"),
            Script(POLL_SCRIPT),
            screen=True,
        )

    @rt("/events/{event_id}/display/latest")
    def latest_display_result(event_id: int):
        if store.get_event(event_id) is None:
            raise HTTPException(status_code=404)
        preview = store.latest_preview(event_id)
        draw = store.latest_draw(event_id)
        if preview and (draw is None or preview["created_at"] >= draw["created_at"]):
            return JSONResponse(preview)
        return JSONResponse(draw or {})
