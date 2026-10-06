import json

from fasthtml.common import (
    H1,
    H2,
    Button,
    Div,
    Fieldset,
    Form,
    HTTPException,
    I,
    Input,
    Legend,
    P,
    Request,
    Small,
    Span,
)

from fastprize.ui import document, redirect_event, status_message


def register_routes(rt, store):
    @rt("/events/{event_id}/import", methods=["GET", "POST"])
    async def import_page(event_id: int, req: Request, status: str = ""):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        if req.method == "POST":
            form = await req.form()
            return await process_uploads(
                event_id,
                {
                    "entrants": form.get("entrants_file"),
                    "prizes": form.get("prizes_file"),
                },
            )
        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Import",
            Div(
                Div("EVENT DATA", cls="upper small-text secondary-text"),
                H1("Import CSV", cls="small"),
                P(f"Load entrants and prizes into {event['name']}."),
                cls="vertical",
            ),
            P(message, cls="tertiary-container padding") if message else "",
            Form(
                Fieldset(
                    Legend("Select CSV files"),
                    Div(
                        Div(
                            H2("Entrants", cls="small"),
                            Small("Required: name. Optional: organization."),
                            Button(
                                I("attach_file"),
                                Span("Entrants CSV"),
                                type="button",
                                onclick="this.nextElementSibling.click()",
                                cls="secondary",
                            ),
                            Input(
                                type="file",
                                name="entrants_file",
                                accept=".csv,text/csv",
                                hidden=True,
                                onchange="this.previousElementSibling.querySelector('span').textContent = this.files[0].name",
                            ),
                            cls="s12 m6 l6 vertical",
                        ),
                        Div(
                            H2("Prizes", cls="small"),
                            Small("Required: name. Optional: sponsor."),
                            Button(
                                I("attach_file"),
                                Span("Prizes CSV"),
                                type="button",
                                onclick="this.nextElementSibling.click()",
                                cls="secondary",
                            ),
                            Input(
                                type="file",
                                name="prizes_file",
                                accept=".csv,text/csv",
                                hidden=True,
                                onchange="this.previousElementSibling.querySelector('span').textContent = this.files[0].name",
                            ),
                            cls="s12 m6 l6 vertical",
                        ),
                        cls="grid",
                    ),
                    Button(
                        I("upload_file"),
                        "Import selected files",
                        type="submit",
                        cls="primary large",
                    ),
                    cls="vertical",
                ),
                action=f"/events/{event_id}/import",
                method="post",
                enctype="multipart/form-data",
                cls="vertical",
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="import",
        )

    async def process_uploads(event_id: int, uploads):
        contents = {}
        for kind, upload in uploads.items():
            if upload is None or not getattr(upload, "filename", ""):
                continue
            try:
                contents[kind] = (await upload.read()).decode("utf-8-sig")
            except UnicodeDecodeError:
                return redirect_event(event_id, "invalid-encoding", "import")

        if not contents:
            return redirect_event(event_id, "no-file", "import")

        reports = {}
        for kind, content in contents.items():
            if kind == "entrants":
                reports[kind] = store.import_entrants(event_id, content)
            else:
                reports[kind] = store.import_prizes(event_id, content)

        if len(reports) == 1:
            kind, report = next(iter(reports.items()))
            if kind == "entrants":
                status = f"entrants-imported:{report.added}:{report.duplicates}:{len(report.errors)}:{'; '.join(report.errors[:3])}"
            else:
                status = f"prizes-imported:{report.added}:0:{len(report.errors)}:{'; '.join(report.errors[:3])}"
        else:
            status = "imports-completed:" + json.dumps(
                {
                    kind: {
                        "added": report.added,
                        "duplicates": report.duplicates,
                        "errors": report.errors[:3],
                    }
                    for kind, report in reports.items()
                },
                separators=(",", ":"),
            )
        return redirect_event(event_id, status, "import")

    async def import_csv(event_id: int, req: Request, kind: str):
        form = await req.form()
        return await process_uploads(event_id, {kind: form.get("file")})

    @rt("/events/{event_id}/entrants/import", methods=["POST"])
    async def import_entrants(event_id: int, req: Request):
        return await import_csv(event_id, req, "entrants")

    @rt("/events/{event_id}/prizes/import", methods=["POST"])
    async def import_prizes(event_id: int, req: Request):
        return await import_csv(event_id, req, "prizes")
