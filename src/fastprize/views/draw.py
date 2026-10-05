from fasthtml.common import (
    H1,
    H2,
    A,
    Button,
    Div,
    Form,
    P,
    Script,
    Section,
    Small,
    Span,
    Strong,
)
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, RedirectResponse

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
        const idle = document.createElement('p');
        idle.className = 'screen-idle';
        idle.textContent = 'The next name could be yours.';
        node.append(idle);
        return node;
    }
    const eyebrow = document.createElement('div');
    eyebrow.className = 'eyebrow';
    eyebrow.textContent = 'The winner is';
    const name = document.createElement('h1');
    name.className = 'winner-name';
    name.textContent = draw.entrant_name;
    const organization = document.createElement('p');
    organization.className = 'winner-org';
    organization.textContent = draw.organization || '';
    const award = document.createElement('div');
    award.className = 'award-line';
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
      requestAnimationFrame(() => current.classList.add('reveal'));
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
            Div(
                Div(
                    Strong(prize["prize_name"]),
                    Small(prize["sponsor"] or "No sponsor listed"),
                    class_="record-info",
                ),
                Form(
                    Button("Select winner", type="submit"),
                    action=f"/events/{event_id}/draws/{prize['id']}/preview",
                    method="post",
                ),
                class_="record",
            )
            for prize in available_prizes
        ]
        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Draw",
            Div(
                Div("LIVE DRAW", class_="eyebrow"),
                H1("Draw a prize"),
                P(f"{eligible_count} eligible entrants"),
                class_="page-intro",
            ),
            P(message, class_="notice") if message else "",
            preview_modal if preview_modal else "",
            Section(
                H2("Available prizes"),
                Div(*prize_rows, class_="record-list")
                if prize_rows
                else P("No prizes are available to draw.", class_="empty"),
                class_="section",
            ),
            A(
                "Open projector display",
                href=f"/events/{event_id}/display",
                class_="button display-link",
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
                Div("LIVE PRIZE DRAW", class_="eyebrow"),
                winner_fragment(current_result),
                class_="screen-content",
            ),
            P("FastPrize | Live draw", class_="screen-footer"),
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
