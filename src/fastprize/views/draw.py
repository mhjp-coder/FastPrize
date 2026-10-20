import segno
from fasthtml.common import (
    A,
    Div,
    Form,
    HTTPException,
    JSONResponse,
    Li,
    NotStr,
    P,
    RedirectResponse,
    Request,
    Script,
    Strong,
    to_xml,
)
from monsterui.franken import H2, Button, ButtonT, Card, Grid, Small, TextT
from starlette.responses import HTMLResponse

from fastprize.ui import (
    award_status,
    brand_mark,
    document,
    draw_preview_modal,
    live_quote,
    page_header,
    paged_list,
    record_body,
    record_row,
    redirect_event,
    search_field,
    stat_card,
    status_banner,
    status_message,
    status_tone,
    winner_fragment,
)

POLL_SCRIPT = """
let current = document.getElementById('live-result');
const banner = document.getElementById('live-banner');
function resultNode(draw) {
    const node = document.createElement('div');
    node.id = 'live-result';
    node.className = 'live-result';
    node.dataset.drawId = draw.id ? String(draw.id) : '';
    node.dataset.resultVersion = draw.created_at || '';
    if (!draw.id) {
        node.dataset.displayState = 'idle';
        const idle = document.createElement('p');
        idle.className = 'live-idle';
        idle.textContent = 'The next name could be yours.';
        node.append(idle);
        return node;
    }
    if (draw.quote) {
        node.dataset.displayState = 'quote';
        const quote = document.createElement('p');
        quote.className = 'live-quote';
        quote.textContent = '"' + draw.quote + '"';
        node.append(quote);
        return node;
    }
    node.dataset.displayState = 'winner';
    const person = document.createElement('div');
    person.className = 'live-person';
    const name = document.createElement('h1');
    name.className = 'live-name';
    name.textContent = draw.entrant_name;
    person.append(name);
    if (draw.organization) {
        const from = document.createElement('p');
        from.className = 'live-join';
        from.textContent = 'from';
        const organization = document.createElement('p');
        organization.className = 'live-org';
        organization.textContent = draw.organization;
        person.append(from, organization);
    }
    const award = document.createElement('div');
    award.className = 'live-award';
    const prize = document.createElement('p');
    prize.className = 'live-prize';
    prize.textContent = draw.prize_name;
    const sponsored = document.createElement('p');
    sponsored.className = 'live-join';
    sponsored.textContent = 'sponsored by';
    const sponsor = document.createElement('p');
    sponsor.className = 'live-sponsor';
    sponsor.textContent = draw.sponsor || 'our conference sponsors';
    award.append(prize, sponsored, sponsor);
    node.append(person, award);
    return node;
}
async function refreshResult() {
  try {
    const response = await fetch(location.pathname + '/latest', {cache: 'no-store'});
    if (!response.ok) return;
    const draw = await response.json();
    banner.hidden = !draw.id || Boolean(draw.quote);
    banner.textContent = draw.id && !draw.quote ? 'The winner is' : '';
    const next = resultNode(draw);
    const changed = next.dataset.resultVersion !== current.dataset.resultVersion
      || next.dataset.displayState !== current.dataset.displayState
      || next.textContent !== current.textContent;
    if (changed) {
      current.replaceWith(next);
      current = next;
    }
  } catch (_) {}
}
setInterval(refreshResult, 1000);
"""


def _display_payload(record: dict | None) -> dict:
    if not record:
        return {}
    payload = dict(record)
    quote = live_quote(record)
    if quote:
        payload["quote"] = quote
    return payload


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
                record_row(
                    record_body(
                        Strong(prize["prize_name"]),
                        Small(prize["sponsor"] or "No sponsor listed", cls=TextT.meta),
                    ),
                    Form(
                        Button("Draw!", cls=ButtonT.primary),
                        action=f"/events/{event_id}/draws/{prize['id']}/preview",
                        method="post",
                    ),
                ),
                data_search=f"{prize['prize_name']} {prize['sponsor'] or ''}".lower(),
            )
            for prize in available_prizes
        ]
        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Draw",
            page_header("Draw a prize"),
            status_banner(message, status_tone(status)),
            Grid(
                stat_card(eligible_count, "eligible entrants"),
                stat_card(len(available_prizes), "prizes remaining"),
                cols_max=2,
                cls="gap-6",
            ),
            preview_modal if preview_modal else "",
            Card(
                Div(
                    search_field("prize-list", "Search prizes"),
                    cls="list-search",
                ),
                paged_list(
                    "prize-list",
                    prize_rows,
                    "No prizes are available to draw.",
                ),
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
            recorded = store.draw(
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
        return redirect_event(
            event_id,
            award_status(recorded["entrant_name"], recorded["organization"]),
            "draw",
        )

    @rt("/events/{event_id}/draws/{prize_id}", methods=["POST"])
    def draw_prize(event_id: int, prize_id: int):
        return preview_draw_prize(event_id, prize_id)

    def live_display_page(event: dict):
        event_id = event["id"]
        preview = store.latest_preview(event_id)
        draw = store.latest_draw(event_id)
        current_result = (
            preview
            if preview and (draw is None or preview["created_at"] >= draw["created_at"])
            else draw
        )
        showing_winner = bool(current_result) and live_quote(current_result) is None
        return document(
            f"{event['name']} | Live draw",
            Div(
                "The winner is" if showing_winner else "",
                id="live-banner",
                cls="live-kicker live-banner",
                hidden=None if showing_winner else True,
            ),
            winner_fragment(current_result),
            Div(
                brand_mark(),
                "FastPrize | Live draw",
                cls="live-footer",
            ),
            Script(POLL_SCRIPT),
            screen=True,
        )

    @rt("/events/{event_id}/display")
    def display(event_id: int):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        return live_display_page(event)

    @rt("/events/{event_id}/display-link")
    def display_link(event_id: int, req: Request):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        slug = store.display_slug(event)
        url = f"{str(req.base_url).rstrip('/')}/{slug}"
        qr = segno.make(url, error="m")
        return HTMLResponse(
            to_xml(
                Div(
                    H2("Live display", cls="dialog-title"),
                    P("Open this link on the projector, or scan the code."),
                    Div(
                        NotStr(qr.svg_inline(scale=5, border=1, omitsize=True)),
                        cls="display-qr",
                    ),
                    A(url, href=url, target="_blank", rel="noopener", cls="display-link"),
                    Button(
                        "Close",
                        type="button",
                        cls=ButtonT.secondary,
                        onclick="this.closest('dialog').close()",
                    ),
                    cls="display-link-modal",
                )
            )
        )

    @rt("/events/{event_id}/display/latest")
    def latest_display_result(event_id: int):
        if store.get_event(event_id) is None:
            raise HTTPException(status_code=404)
        preview = store.latest_preview(event_id)
        draw = store.latest_draw(event_id)
        if preview and (draw is None or preview["created_at"] >= draw["created_at"]):
            return JSONResponse(_display_payload(preview))
        return JSONResponse(_display_payload(draw))

    @rt("/{slug}/latest")
    def latest_display_by_slug(slug: str):
        event = store.get_event_by_slug(slug)
        if event is None:
            raise HTTPException(status_code=404)
        return latest_display_result(event["id"])

    @rt("/{slug}")
    def display_by_slug(slug: str):
        event = store.get_event_by_slug(slug)
        if event is None:
            raise HTTPException(status_code=404)
        return live_display_page(event)
