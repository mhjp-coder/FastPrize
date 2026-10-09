from fasthtml.common import (
    H1,
    H2,
    Article,
    Button,
    Details,
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
    Summary,
)

from fastprize.ui import document, redirect_event, status_message


def register_routes(rt, store):
    def entrant_info(entrant):
        return Div(
            Strong(entrant["name"]),
            Small(entrant["organization"] or "No organization listed"),
            cls="vertical",
            id=f"entrant-info-{entrant['id']}",
        )

    def find_entrant(event_id, entrant_id):
        return next(
            (
                entrant
                for entrant in store.entrants(event_id)
                if entrant["id"] == entrant_id
            ),
            None,
        )

    def entrant_count_text(event_id):
        entrants = store.entrants(event_id)
        eligible_count = sum(entrant["eligible"] for entrant in entrants)
        return f"{len(entrants)} total | {eligible_count} eligible"

    def entrant_count_update(event_id):
        return P(
            entrant_count_text(event_id),
            id="entrant-counts",
            hx_swap_oob="outerHTML",
        )

    def entrant_row(event_id, entrant, include_count=False):
        entrant_id = entrant["id"]
        eligibility_dialog = f"eligibility-dialog-{entrant_id}"
        target_eligibility = "not eligible" if entrant["eligible"] else "eligible"
        return Article(
            entrant_info(entrant),
            Div(
                Div(
                    Button(
                        "Eligible" if entrant["eligible"] else "Not eligible",
                        type="button",
                        aria_pressed="true" if entrant["eligible"] else "false",
                        aria_haspopup="dialog",
                        aria_controls=eligibility_dialog,
                        data_ui=f"#{eligibility_dialog}",
                        cls="primary" if entrant["eligible"] else "error",
                    ),
                    Dialog(
                        H2("Change eligibility?", cls="small"),
                        P(f"Mark {entrant['name']} {target_eligibility}?"),
                        Nav(
                            Button(
                                "Cancel",
                                type="button",
                                data_ui=f"#{eligibility_dialog}",
                                cls="text",
                            ),
                            Form(
                                Button(
                                    f"Mark {target_eligibility}",
                                    type="submit",
                                    cls="error" if entrant["eligible"] else "primary",
                                ),
                                action=f"/events/{event_id}/entrants/{entrant_id}/toggle-eligibility",
                                method="post",
                                hx_post=f"/events/{event_id}/entrants/{entrant_id}/toggle-eligibility",
                                hx_target=f"#entrant-row-{entrant_id}",
                                hx_swap="outerHTML",
                            ),
                            cls="horizontal",
                        ),
                        id=eligibility_dialog,
                        aria_label=f"Confirm changing eligibility for {entrant['name']}",
                        cls="modal padding medium-width left-align",
                    ),
                ),
                Div(
                    Button(
                        I("edit"),
                        type="button",
                        title=f"Edit {entrant['name']}",
                        aria_label=f"Edit {entrant['name']}",
                        cls="button circle primary",
                        hx_get=f"/events/{event_id}/entrants/{entrant_id}/edit",
                        hx_target=f"#entrant-info-{entrant_id}",
                        hx_swap="outerHTML",
                        data_edit_target=f"entrant-info-{entrant_id}",
                    ),
                    data_hide_while_editing=f"entrant-info-{entrant_id}",
                ),
                Div(
                    Button(
                        I("delete"),
                        type="button",
                        title=f"Remove {entrant['name']}",
                        aria_label=f"Remove {entrant['name']}",
                        aria_haspopup="dialog",
                        aria_controls=f"remove-entrant-dialog-{entrant_id}",
                        data_ui=f"#remove-entrant-dialog-{entrant_id}",
                        cls="circle error",
                    ),
                    Dialog(
                        H2("Remove entrant?", cls="small"),
                        P(
                            f"Remove {entrant['name']} from this event? "
                            "This cannot be undone."
                        ),
                        Nav(
                            Button(
                                "Cancel",
                                type="button",
                                data_ui=f"#remove-entrant-dialog-{entrant_id}",
                                cls="text",
                            ),
                            Form(
                                Button(
                                    I("delete"),
                                    Span("Remove"),
                                    type="submit",
                                    cls="error",
                                ),
                                action=f"/events/{event_id}/entrants/{entrant_id}/remove",
                                method="post",
                                hx_post=f"/events/{event_id}/entrants/{entrant_id}/remove",
                                hx_target=f"#entrant-row-{entrant_id}",
                                hx_swap="delete",
                            ),
                            cls="horizontal",
                        ),
                        id=f"remove-entrant-dialog-{entrant_id}",
                        aria_label=f"Confirm removing {entrant['name']}",
                        cls="modal padding medium-width left-align",
                    ),
                    data_hide_while_editing=f"entrant-info-{entrant_id}",
                ),
                cls="horizontal middle-align small-space top-margin right-align bottom-margin",
            ),
            entrant_count_update(event_id) if include_count else "",
            cls="s12 m12 l6 card padding tertiary-container small-round vertical",
            id=f"entrant-row-{entrant_id}",
        )

    def entrant_list(event_id, entrants, search=""):
        if entrants:
            content = [entrant_row(event_id, entrant) for entrant in entrants]
        elif search:
            content = [P("No entrants match your search.", cls="s12 secondary-text")]
        else:
            content = [
                P("No entrants yet.", cls="s12 secondary-text"),
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
        return Div(*content, cls="grid small-space", id="entrant-list")

    @rt("/events/{event_id}/entrants", methods=["GET"])
    def entrants_page(event_id: int, status: str = ""):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        entrants = store.entrants(event_id)
        eligible_count = sum(entrant["eligible"] for entrant in entrants)

        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Entrants",
            Article(
                H1("Entrants", cls="small"),
                P(
                    f"{len(entrants)} total | {eligible_count} eligible",
                    id="entrant-counts",
                ),
                cls="card padding primary-container small-round vertical bottom-margin",
            ),
            P(message, cls="tertiary-container padding") if message else "",
            Details(
                Summary(
                    I("expand_more", data_add_expansion_chevron=True),
                    Span("Add entrant"),
                    cls="button primary responsive none",
                    aria_expanded="false",
                ),
                Article(
                    Form(
                        Div(
                            Input(
                                id="entrant-name",
                                name="name",
                                required=True,
                                type="text",
                            ),
                            Label("Full name", fr="entrant-name"),
                            cls="s6 m6 l6 field label border fill round extra",
                        ),
                        Div(
                            Input(
                                id="entrant-organization",
                                name="organization",
                                type="text",
                                aria_label="Organization (optional)",
                            ),
                            Label("Organization", fr="entrant-organization"),
                            cls="s6 m6 l6 field label border fill round extra",
                        ),
                        Button(
                            I("person_add"),
                            Span("Add entrant"),
                            type="submit",
                            cls="s12 responsive extra primary",
                        ),
                        action=f"/events/{event_id}/entrants",
                        method="post",
                        cls="grid small-space bottom-padding",
                    ),
                    cls="card padding secondary-container small-round vertical bottom-padding",
                ),
                id="entrant-add-expansion",
                data_add_expansion="true",
                cls="vertical bottom-margin",
            ),
            Article(
                Div(
                    H2("Entrant list", cls="s12 m6 small"),
                    Div(
                        I("search", cls="front"),
                        Input(
                            id="entrant-search",
                            name="search",
                            type="search",
                            placeholder="Search entrants",
                            aria_label="Search entrants",
                            autocomplete="off",
                            hx_get=f"/events/{event_id}/entrants/search",
                            hx_trigger="input changed delay:300ms",
                            hx_target="#entrant-list",
                            hx_swap="outerHTML",
                        ),
                        cls="s12 m6 field large prefix round fill border active",
                    ),
                    cls="grid middle-align",
                ),
                entrant_list(event_id, entrants),
                cls="card padding secondary-container small-round vertical bottom-padding",
            ),
            event_id=event_id,
            active_link="entrants",
        )

    @rt("/events/{event_id}/entrants/search", methods=["GET"])
    def search_entrants(event_id: int, search: str = ""):
        if store.get_event(event_id) is None:
            raise HTTPException(status_code=404)
        query = search.strip().casefold()
        entrants = [
            entrant
            for entrant in store.entrants(event_id)
            if query in entrant["name"].casefold()
            or query in (entrant["organization"] or "").casefold()
        ]
        return entrant_list(event_id, entrants, search)

    @rt("/events/{event_id}/entrants", methods=["POST"])
    def add_entrant(event_id: int, name: str, organization: str = ""):
        try:
            added = store.add_entrant(event_id, name, organization)
        except ValueError:
            return redirect_event(event_id, "invalid-entrant", "entrants")
        return redirect_event(
            event_id,
            "entrant-added" if added else "invalid-entrant",
            "entrants",
        )

    @rt("/events/{event_id}/entrants/{entrant_id}/edit", methods=["GET"])
    def edit_entrant_form(event_id: int, entrant_id: int):
        entrant = find_entrant(event_id, entrant_id)
        if entrant is None:
            raise HTTPException(status_code=404)
        return Form(
            Div(
                Div(
                    Input(
                        name="name",
                        value=entrant["name"],
                        required=True,
                        aria_label="Entrant name",
                    ),
                    cls="field round fill border",
                ),
                Div(
                    Input(
                        name="organization",
                        value=entrant["organization"],
                        aria_label="Organization",
                    ),
                    cls="field round fill border",
                ),
                cls="s8 m9 l9 vertical",
            ),
            Div(
                Button(
                    I("save"),
                    type="submit",
                    aria_label="Save entrant",
                    title="Save entrant",
                    cls="circle primary",
                ),
                Div(cls="small-space"),
                Button(
                    I("close"),
                    type="button",
                    aria_label="Cancel edit",
                    title="Cancel edit",
                    hx_get=f"/events/{event_id}/entrants/{entrant_id}/display",
                    hx_target=f"#entrant-info-{entrant_id}",
                    hx_swap="outerHTML",
                    cls="circle",
                ),
                cls="s4 m3 l3 vertical",
            ),
            action=f"/events/{event_id}/entrants/{entrant_id}/edit",
            method="post",
            hx_post=f"/events/{event_id}/entrants/{entrant_id}/edit",
            hx_target=f"#entrant-row-{entrant_id}",
            hx_swap="outerHTML",
            cls="grid middle-align small-space",
            id=f"entrant-info-{entrant_id}",
            data_inline_edit=True,
        )

    @rt("/events/{event_id}/entrants/{entrant_id}/display", methods=["GET"])
    def entrant_display(event_id: int, entrant_id: int):
        entrant = find_entrant(event_id, entrant_id)
        if entrant is None:
            raise HTTPException(status_code=404)
        return entrant_info(entrant)

    @rt("/events/{event_id}/entrants/{entrant_id}/edit", methods=["POST"])
    def edit_entrant(
        event_id: int,
        entrant_id: int,
        req: Request,
        name: str,
        organization: str = "",
    ):
        try:
            updated = store.update_entrant(event_id, entrant_id, name, organization)
        except ValueError:
            return redirect_event(event_id, "invalid-entrant", "entrants")
        if req.headers.get("HX-Request") == "true" and updated:
            return entrant_row(event_id, find_entrant(event_id, entrant_id))
        return redirect_event(
            event_id,
            "entrant-updated" if updated else "invalid-entrant",
            "entrants",
        )

    @rt("/events/{event_id}/entrants/{entrant_id}/toggle-eligibility", methods=["POST"])
    def toggle_entrant_eligibility(event_id: int, entrant_id: int, req: Request):
        updated = store.toggle_entrant_eligibility(event_id, entrant_id)
        if req.headers.get("HX-Request") == "true" and updated:
            return entrant_row(
                event_id,
                find_entrant(event_id, entrant_id),
                include_count=True,
            )
        return redirect_event(
            event_id,
            "entrant-eligibility-updated" if updated else "entrant-missing",
            "entrants",
        )

    @rt("/events/{event_id}/entrants/{entrant_id}/remove", methods=["POST"])
    def remove_entrant(event_id: int, entrant_id: int, req: Request):
        store.remove_entrant(event_id, entrant_id)
        if req.headers.get("HX-Request") == "true":
            return entrant_count_update(event_id)
        return redirect_event(event_id, "entrant-removed", "entrants")
