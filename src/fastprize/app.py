import os
from pathlib import Path
from urllib.parse import quote

from fasthtml.common import (
    A,
    Body,
    Button,
    Details,
    Div,
    Form,
    H1,
    H2,
    Head,
    Html,
    Input,
    Label,
    Main,
    Meta,
    Option,
    P,
    Script,
    Section,
    Select,
    Small,
    Span,
    Strong,
    Style,
    Summary,
    Title,
    fast_app,
    serve,
)
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from fastprize.store import PrizeDrawStore


CSS = """
:root{font-family:'Avenir Next',Avenir,'Trebuchet MS',sans-serif;color:#172d2a;background:#f3f5ef;--ink:#172d2a;--muted:#64736e;--line:#d6dfd8;--paper:#fffefa;--green:#176c58;--coral:#d6503c;--sun:#edbb4b}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background-image:radial-gradient(#dce5dc 0.7px,transparent 0.7px);background-size:18px 18px}
a{color:inherit}header.topbar{display:flex;align-items:center;justify-content:space-between;padding:17px clamp(20px,5vw,72px);border-bottom:1px solid var(--line);background:#f8f8f2eF}
.brand{display:flex;align-items:center;gap:11px;text-decoration:none;font-size:17px;font-weight:800}.brand-mark{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:var(--green);color:white;font-size:15px}
.topbar nav{display:flex;gap:20px;font-size:13px;color:var(--muted)}.topbar nav a{text-decoration:none}.topbar nav a:hover{color:var(--green)}
main{width:min(1180px,calc(100% - 40px));margin:34px auto 80px}.eyebrow{text-transform:uppercase;letter-spacing:0;font-size:11px;font-weight:800;color:var(--green)}
h1{font-family:Georgia,'Times New Roman',serif;font-size:48px;line-height:1.04;letter-spacing:0;margin:8px 0 12px}h2{font-family:Georgia,'Times New Roman',serif;font-size:21px;margin:0;letter-spacing:0}h3{font-size:15px;margin:0}p{line-height:1.5}.muted,.subtle{color:var(--muted)}.page-intro{margin-bottom:26px}.page-intro p{margin:0;color:var(--muted)}
.event-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:10px;margin-top:25px}.event-link{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:18px 20px;border:1px solid var(--line);background:var(--paper);text-decoration:none;transition:transform .16s,border-color .16s}.event-link:hover{transform:translateY(-2px);border-color:var(--green)}.event-link strong{font-size:16px}.event-link span{font-size:12px;color:var(--muted)}
.create-event{display:flex;gap:10px;max-width:520px;margin-top:28px}.control,input,select{font:inherit;color:var(--ink);border:1px solid #cbd6ce;background:#fffefa;border-radius:5px;padding:11px 12px;min-width:0}.create-event input{flex:1}
button,.button{display:inline-flex;align-items:center;justify-content:center;gap:8px;border:0;border-radius:4px;padding:10px 14px;background:var(--green);color:white;font-family:inherit;font-size:13px;font-weight:700;cursor:pointer;text-decoration:none;min-height:40px}button:hover,.button:hover{background:#105642}button.secondary{background:#e6eee8;color:var(--ink)}button.secondary:hover{background:#d9e6dc}button.danger{background:#f6e4df;color:#a3392c}button.danger:hover{background:#f0d1c9}button:disabled{opacity:.45;cursor:not-allowed}
.event-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:22px}.event-heading h1{margin-bottom:6px}.display-link{white-space:nowrap;margin-top:16px;background:var(--coral)}.display-link:hover{background:#b83f30}
.notice{padding:11px 14px;border-left:3px solid var(--green);background:#e4eee6;margin:0 0 20px;font-size:14px}.notice.error{border-color:var(--coral);background:#f8e9e4}
.settings{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:14px 0;border-block:1px solid var(--line);margin:0 0 24px}.settings label{font-size:13px;font-weight:700}.settings form{display:flex;gap:8px;align-items:center}.settings select{padding:8px 10px}
.workspace{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:34px}.column{min-width:0}.section{padding:0 0 24px;margin-bottom:24px;border-bottom:1px solid var(--line)}.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:14px}.section-head small{color:var(--muted)}
.entry-form{display:grid;grid-template-columns:1fr 1fr auto;gap:7px;margin:0 0 13px}.entry-form input{width:100%;padding:9px 10px;font-size:13px}.entry-form button{grid-column:1/-1;justify-self:start}.import-form{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 15px}.import-form input{flex:1;max-width:300px;padding:8px;font-size:12px}.import-form button{min-height:35px;padding:8px 11px;font-size:12px}
.record-list{display:grid;gap:7px}.record{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:12px;padding:11px 12px;background:var(--paper);border:1px solid var(--line)}.record-info{min-width:0}.record-info strong{display:block;overflow-wrap:anywhere;font-size:14px}.record-info small{display:block;color:var(--muted);font-size:12px;margin-top:3px}.record-actions{display:flex;gap:5px;align-items:center}.record-actions button{min-height:31px;padding:6px 9px;font-size:11px}.record details{grid-column:1/-1}.record summary{cursor:pointer;color:var(--green);font-size:12px;font-weight:700}.edit-form{display:flex;gap:6px;flex-wrap:wrap;padding-top:8px}.edit-form input{flex:1;width:130px;padding:8px;font-size:12px}.edit-form button{min-height:34px}.badge{display:inline-block;border-radius:20px;padding:4px 8px;background:#e6eee8;color:var(--green);font-size:10px;font-weight:800;text-transform:uppercase}.badge.awarded{background:#f6e7c2;color:#76510a}
.history{width:100%;font-size:13px}.history-row{display:grid;grid-template-columns:1.2fr 1.2fr 1fr;gap:10px;padding:10px 7px;border-bottom:1px solid var(--line);align-items:start}.history-title{font-size:10px;text-transform:uppercase;color:var(--muted);letter-spacing:0}.history-cell{min-width:0;overflow-wrap:anywhere}.history-cell small{display:block;color:var(--muted);margin-top:3px}.empty{padding:15px 0;color:var(--muted);font-size:13px}
.screen{width:100%;min-height:100vh;margin:0;padding:70px 7vw;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;background:radial-gradient(ellipse at 50% 105%,#f5d879 0,transparent 42%),#f2f4ed}.screen-brand{position:absolute;top:28px;left:5vw;font-size:14px;font-weight:800;display:flex;gap:9px;align-items:center;text-decoration:none}.screen-brand .brand-mark{background:var(--coral)}.screen-content{width:min(980px,100%)}.screen h1{font-size:76px;margin:14px 0 26px;line-height:1.04;letter-spacing:0}.reveal{animation:reveal .8s cubic-bezier(.2,.8, .2,1) both}.screen .eyebrow{color:var(--coral)}.winner-name{font-weight:700}.winner-org{font-size:26px;color:var(--muted);margin:0}.award-line{display:inline-flex;align-items:center;gap:11px;flex-wrap:wrap;justify-content:center;margin-top:48px;padding:14px 20px;border-top:1px solid #b9c7bb;border-bottom:1px solid #b9c7bb;font-size:20px}.award-line strong{color:var(--green)}.screen-idle{font-size:22px;color:var(--muted);margin:0}.screen-footer{position:absolute;bottom:22px;color:var(--muted);font-size:12px}.back-link{position:absolute;top:28px;right:5vw;color:var(--muted);font-size:13px;text-decoration:none}
@keyframes reveal{0%{opacity:0;transform:translateY(22px) scale(.98)}65%{opacity:1;transform:translateY(-3px) scale(1.005)}100%{opacity:1;transform:translateY(0) scale(1)}}
@media(max-width:760px){main{margin-top:25px}h1{font-size:38px}.workspace{grid-template-columns:1fr;gap:0}.event-heading{flex-direction:column}.display-link{margin:0}.settings{align-items:flex-start;flex-direction:column}.entry-form{grid-template-columns:1fr 1fr}.entry-form button{grid-column:1/-1}.screen h1{font-size:44px}.winner-org{font-size:19px}.award-line{font-size:16px;margin-top:28px}.screen-footer{position:static;margin-top:50px}.history-row{grid-template-columns:1fr 1fr}.history-row > :last-child{display:none}}
"""

POLL_SCRIPT = """
let current = document.getElementById('live-result');
function resultNode(draw) {
    const node = document.createElement('div');
    node.id = 'live-result';
    node.dataset.drawId = draw.id ? String(draw.id) : '';
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
        if (next.dataset.drawId !== current.dataset.drawId) {
      current.replaceWith(next);
      current = next;
      requestAnimationFrame(() => current.classList.add('reveal'));
    }
  } catch (_) {}
}
setInterval(refreshResult, 1000);
"""

STATUS_MESSAGES = {
    "event-created": "Event created.",
    "entrant-added": "Entrant added.",
    "entrant-updated": "Entrant updated.",
    "entrant-removed": "Entrant removed.",
    "prize-added": "Prize added.",
    "prize-updated": "Prize updated.",
    "prize-removed": "Prize removed.",
    "settings-updated": "Winner eligibility setting updated.",
    "entrants-imported": "Entrant CSV imported.",
    "prizes-imported": "Prize CSV imported.",
    "draw-complete": "The draw is complete. The projector is updating now.",
    "no-eligible-entrants": "Add an eligible entrant before drawing this prize.",
    "no-file": "Choose a CSV file to import.",
    "invalid-entrant": "Entrant name is required, and duplicate names are skipped.",
    "invalid-prize": "Prize name is required.",
    "prize-locked": "Awarded prizes cannot be changed or removed.",
    "invalid-encoding": "The CSV file must use UTF-8 text encoding.",
    "event-missing": "That event could not be found.",
}


def _redirect_event(event_id: int, status: str) -> RedirectResponse:
    return RedirectResponse(
        f"/events/{event_id}?status={quote(status, safe='')}", status_code=303
    )


def _status_message(status: str) -> str:
    if status.startswith("entrants-imported:") or status.startswith("prizes-imported:"):
        kind, added, duplicates, error_count, *details = status.split(":", 4)
        label = "entrant" if kind == "entrants-imported" else "prize"
        message = (
            f"Imported {added} {label}{'' if added == '1' else 's'}; "
            f"{duplicates} duplicate row{'s' if duplicates != '1' else ''} skipped; "
            f"{error_count} invalid row{'s' if error_count != '1' else ''}."
        )
        if details and details[0]:
            message += " " + details[0]
        return message
    return STATUS_MESSAGES.get(status, "")


def _record_list(records: list[dict], empty_message: str, render_record):
    if not records:
        return P(empty_message, class_="empty")
    return Div(*(render_record(record) for record in records), class_="record-list")


def _winner_fragment(draw: dict | None):
    if draw is None:
        return Div(
            P("The next name could be yours.", class_="screen-idle"),
            id="live-result",
            **{"data-draw-id": ""},
        )
    return Div(
        Div("The winner is", class_="eyebrow"),
        H1(draw["entrant_name"], class_="winner-name"),
        P(draw["organization"] or "", class_="winner-org"),
        Div(
            Strong(draw["prize_name"]),
            Span("from"),
            Strong(draw["sponsor"] or "our conference sponsors"),
            class_="award-line",
        ),
        id="live-result",
        **{"data-draw-id": str(draw["id"])},
    )


def create_app(db_path: str | Path | None = None):
    database = db_path or os.environ.get("FASTPRIZE_DB_PATH", "fastprize.sqlite3")
    store = PrizeDrawStore(database)
    app, rt = fast_app(title="FastPrize", pico=False, surreal=False, htmx=False)

    def document(title: str, *content, screen: bool = False):
        body_content = (
            content
            if screen
            else (
                Div(
                    A(
                        Span("F", class_="brand-mark"),
                        "FastPrize",
                        href="/",
                        class_="brand",
                    ),
                    Div(
                        A("Events", href="/"),
                        class_="top-links",
                    ),
                    class_="topbar",
                ),
                Main(*content),
            )
        )
        return Html(
            Head(
                Meta(charset="utf-8"),
                Meta(name="viewport", content="width=device-width, initial-scale=1"),
                Title(title),
                Style(CSS),
            ),
            Body(*body_content, class_="screen" if screen else "app"),
        )

    @rt("/")
    def home():
        events = store.list_events()
        event_links = [
            A(
                Div(Strong(event["name"]), Span("Open event workspace")),
                Span("Open"),
                href=f"/events/{event['id']}",
                class_="event-link",
            )
            for event in events
        ]
        return document(
            "FastPrize | Events",
            Div(
                Div("CONFERENCE DRAW CONTROL", class_="eyebrow"),
                H1("Make the moment count."),
                P("Run a draw, send the winner to the big screen."),
                class_="page-intro",
            ),
            Section(
                H2("Your events"),
                Div(*event_links, class_="event-grid")
                if event_links
                else P(
                    "No events yet. Create one to start adding entrants and prizes.",
                    class_="empty",
                ),
            ),
            Form(
                Input(
                    name="name", placeholder="Conference or event name", required=True
                ),
                Button("Create event", type="submit"),
                action="/events",
                method="post",
                class_="create-event",
            ),
        )

    @rt("/events", methods=["POST"])
    def create_event(name: str):
        try:
            event_id = store.create_event(name)
        except ValueError:
            return RedirectResponse("/", status_code=303)
        return _redirect_event(event_id, "event-created")

    @rt("/events/{event_id}")
    def event_workspace(event_id: int, status: str = ""):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        entrants = store.entrants(event_id)
        prizes = store.prizes(event_id)
        history = store.draw_history(event_id)
        available_prizes = [prize for prize in prizes if not prize["drawn"]]
        eligible_count = sum(entrant["eligible"] for entrant in entrants)
        message = _status_message(status)

        def entrant_row(entrant):
            return Div(
                Div(
                    Strong(entrant["name"]),
                    Small(entrant["organization"] or "No organization listed"),
                    class_="record-info",
                ),
                Div(
                    Span(
                        "Eligible" if entrant["eligible"] else "Winner", class_="badge"
                    ),
                    Form(
                        Button("Remove", type="submit", class_="danger"),
                        action=f"/events/{event_id}/entrants/{entrant['id']}/remove",
                        method="post",
                    ),
                    class_="record-actions",
                ),
                Details(
                    Summary("Edit"),
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
                        Button("Save", type="submit", class_="secondary"),
                        action=f"/events/{event_id}/entrants/{entrant['id']}/edit",
                        method="post",
                        class_="edit-form",
                    ),
                ),
                class_="record",
            )

        def prize_row(prize):
            actions = (
                [Span("Awarded", class_="badge awarded")]
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
                                value=prize["name"],
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
                    Strong(prize["name"]),
                    Small(prize["sponsor"] or "No sponsor listed"),
                    class_="record-info",
                ),
                Div(*actions, class_="record-actions"),
                *edit_form,
                class_="record",
            )

        return document(
            f"FastPrize | {event['name']}",
            Div(
                Div(
                    Div("EVENT WORKSPACE", class_="eyebrow"),
                    H1(event["name"]),
                    P(
                        f"{eligible_count} eligible entrants | {len(available_prizes)} prizes available"
                    ),
                ),
                A(
                    "Open projector display",
                    href=f"/events/{event_id}/display",
                    class_="button display-link",
                ),
                class_="event-heading",
            ),
            P(message, class_="notice") if message else "",
            Div(
                Label("Winner eligibility after a draw", for_="remove_winners"),
                Form(
                    Select(
                        Option(
                            "Remove winner from future draws",
                            value="1",
                            selected=bool(event["remove_winners"]),
                        ),
                        Option(
                            "Keep winner eligible",
                            value="0",
                            selected=not bool(event["remove_winners"]),
                        ),
                        name="remove_winners",
                        id="remove_winners",
                    ),
                    Button("Save setting", type="submit", class_="secondary"),
                    action=f"/events/{event_id}/settings",
                    method="post",
                ),
                class_="settings",
            ),
            Div(
                Div(
                    Section(
                        Div(
                            H2("Entrants"),
                            Small(f"{len(entrants)} total | {eligible_count} eligible"),
                            class_="section-head",
                        ),
                        Form(
                            Input(name="name", placeholder="Full name", required=True),
                            Input(
                                name="organization",
                                placeholder="Organization (optional)",
                            ),
                            Button("Add entrant", type="submit"),
                            action=f"/events/{event_id}/entrants",
                            method="post",
                            class_="entry-form",
                        ),
                        Form(
                            Input(
                                type="file",
                                name="file",
                                accept=".csv,text/csv",
                                required=True,
                            ),
                            Button("Import CSV", type="submit", class_="secondary"),
                            action=f"/events/{event_id}/entrants/import",
                            method="post",
                            enctype="multipart/form-data",
                            class_="import-form",
                        ),
                        _record_list(entrants, "No entrants yet.", entrant_row),
                        class_="section",
                    ),
                    Section(
                        Div(
                            H2("Draw history"),
                            Small(f"{len(history)} completed"),
                            class_="section-head",
                        ),
                        Div(
                            Div(
                                Div("Winner", class_="history-head"),
                                Div("Prize", class_="history-head"),
                                Div("Time", class_="history-head"),
                                class_="history-row history-title",
                            ),
                            *(
                                Div(
                                    Div(
                                        Strong(draw["entrant_name"]),
                                        Small(draw["organization"]),
                                        class_="history-cell",
                                    ),
                                    Div(
                                        Strong(draw["prize_name"]),
                                        Small(draw["sponsor"]),
                                        class_="history-cell",
                                    ),
                                    Div(
                                        draw["created_at"].replace("T", " ")[:16],
                                        class_="history-cell",
                                    ),
                                    class_="history-row",
                                )
                                for draw in history
                            ),
                            class_="history",
                        )
                        if history
                        else P("Completed draws will appear here.", class_="empty"),
                        class_="section",
                    ),
                    class_="column",
                ),
                Div(
                    Section(
                        Div(
                            H2("Prizes"),
                            Small(f"{len(available_prizes)} available"),
                            class_="section-head",
                        ),
                        Form(
                            Input(name="name", placeholder="Prize name", required=True),
                            Input(name="sponsor", placeholder="Sponsor (optional)"),
                            Button("Add prize", type="submit"),
                            action=f"/events/{event_id}/prizes",
                            method="post",
                            class_="entry-form",
                        ),
                        Form(
                            Input(
                                type="file",
                                name="file",
                                accept=".csv,text/csv",
                                required=True,
                            ),
                            Button("Import CSV", type="submit", class_="secondary"),
                            action=f"/events/{event_id}/prizes/import",
                            method="post",
                            enctype="multipart/form-data",
                            class_="import-form",
                        ),
                        _record_list(prizes, "No prizes yet.", prize_row),
                        class_="section",
                    ),
                    class_="column",
                ),
                class_="workspace",
            ),
        )

    @rt("/events/{event_id}/settings", methods=["POST"])
    def update_settings(event_id: int, remove_winners: int):
        store.set_remove_winners(event_id, bool(remove_winners))
        return _redirect_event(event_id, "settings-updated")

    @rt("/events/{event_id}/entrants", methods=["POST"])
    def add_entrant(event_id: int, name: str, organization: str = ""):
        try:
            added = store.add_entrant(event_id, name, organization)
        except ValueError:
            return _redirect_event(event_id, "invalid-entrant")
        return _redirect_event(
            event_id, "entrant-added" if added else "invalid-entrant"
        )

    @rt("/events/{event_id}/entrants/{entrant_id}/edit", methods=["POST"])
    def edit_entrant(event_id: int, entrant_id: int, name: str, organization: str = ""):
        try:
            updated = store.update_entrant(event_id, entrant_id, name, organization)
        except ValueError:
            return _redirect_event(event_id, "invalid-entrant")
        return _redirect_event(
            event_id, "entrant-updated" if updated else "invalid-entrant"
        )

    @rt("/events/{event_id}/entrants/{entrant_id}/remove", methods=["POST"])
    def remove_entrant(event_id: int, entrant_id: int):
        store.remove_entrant(event_id, entrant_id)
        return _redirect_event(event_id, "entrant-removed")

    @rt("/events/{event_id}/entrants/import", methods=["POST"])
    async def import_entrants(event_id: int, req: Request):
        form = await req.form()
        upload = form.get("file")
        if upload is None or not getattr(upload, "filename", ""):
            return _redirect_event(event_id, "no-file")
        try:
            content = (await upload.read()).decode("utf-8-sig")
        except UnicodeDecodeError:
            return _redirect_event(event_id, "invalid-encoding")
        report = store.import_entrants(event_id, content)
        details = "; ".join(report.errors[:3])
        status = f"entrants-imported:{report.added}:{report.duplicates}:{len(report.errors)}:{details}"
        return _redirect_event(event_id, status)

    @rt("/events/{event_id}/prizes", methods=["POST"])
    def add_prize(event_id: int, name: str, sponsor: str = ""):
        try:
            store.add_prize(event_id, name, sponsor)
        except ValueError:
            return _redirect_event(event_id, "invalid-prize")
        return _redirect_event(event_id, "prize-added")

    @rt("/events/{event_id}/prizes/{prize_id}/edit", methods=["POST"])
    def edit_prize(event_id: int, prize_id: int, name: str, sponsor: str = ""):
        try:
            updated = store.update_prize(event_id, prize_id, name, sponsor)
        except ValueError:
            return _redirect_event(event_id, "invalid-prize")
        return _redirect_event(event_id, "prize-updated" if updated else "prize-locked")

    @rt("/events/{event_id}/prizes/{prize_id}/remove", methods=["POST"])
    def remove_prize(event_id: int, prize_id: int):
        removed = store.remove_prize(event_id, prize_id)
        return _redirect_event(event_id, "prize-removed" if removed else "prize-locked")

    @rt("/events/{event_id}/prizes/import", methods=["POST"])
    async def import_prizes(event_id: int, req: Request):
        form = await req.form()
        upload = form.get("file")
        if upload is None or not getattr(upload, "filename", ""):
            return _redirect_event(event_id, "no-file")
        try:
            content = (await upload.read()).decode("utf-8-sig")
        except UnicodeDecodeError:
            return _redirect_event(event_id, "invalid-encoding")
        report = store.import_prizes(event_id, content)
        details = "; ".join(report.errors[:3])
        status = f"prizes-imported:{report.added}:0:{len(report.errors)}:{details}"
        return _redirect_event(event_id, status)

    @rt("/events/{event_id}/draws/{prize_id}", methods=["POST"])
    def draw_prize(event_id: int, prize_id: int):
        try:
            store.draw(event_id, prize_id)
        except ValueError:
            return _redirect_event(event_id, "no-eligible-entrants")
        return _redirect_event(event_id, "draw-complete")

    @rt("/events/{event_id}/display")
    def display(event_id: int):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        return document(
            f"{event['name']} | Live draw",
            A(
                Span("F", class_="brand-mark"),
                event["name"],
                class_="screen-brand",
                href=f"/events/{event_id}",
            ),
            A("Operator view", href=f"/events/{event_id}", class_="back-link"),
            Div(
                Div("LIVE PRIZE DRAW", class_="eyebrow"),
                _winner_fragment(store.latest_draw(event_id)),
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
        return JSONResponse(store.latest_draw(event_id) or {})

    return app, store


app, store = create_app()


def main() -> None:
    serve()
