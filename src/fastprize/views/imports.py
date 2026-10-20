import json

from fasthtml.common import (
    Div,
    Form,
    Input,
    P,
    RedirectResponse,
    Request,
    Span,
)
from monsterui.franken import H2, H3, Button, ButtonT, Card, FlexT, Grid, UkIcon

from fastprize.ui import hstack, redirect_event


def _column_info(title: str, *details: str):
    return Span(
        UkIcon("info"),
        aria_label=f"{title} CSV columns",
        cls="info-trigger",
        tabindex="0",
        data_uk_tooltip="title: " + "<br><br>".join(details),
    )


def _file_picker(label: str, name: str, *details: str):
    return Div(
        hstack(
            H3(label),
            _column_info(label, *details),
        ),
        Button(
            UkIcon("paperclip"),
            Span(f"{label} CSV"),
            type="button",
            onclick="this.nextElementSibling.click()",
            cls=ButtonT.secondary,
        ),
        Input(
            type="file",
            name=name,
            accept=".csv,text/csv",
            hidden=True,
            onchange="this.previousElementSibling.querySelector('span').textContent = this.files[0].name",
        ),
        cls=(FlexT.block, FlexT.column, FlexT.top, "gap-3"),
    )


def import_form(event_id: int):
    return Card(
        H2("Import"),
        P("Load entrants and prizes from CSV files."),
        Form(
            Grid(
                _file_picker(
                    "Entrants",
                    "entrants_file",
                    "Name is required. Organization is optional.",
                    "CSV columns: name, organization",
                ),
                _file_picker(
                    "Prizes",
                    "prizes_file",
                    "Prize name is required. Sponsor and prize number are optional.",
                    "CSV columns: prize_name, sponsor, number or prize_number",
                ),
                cols_max=2,
                cls="gap-6",
            ),
            Button("Import selected files", cls=(ButtonT.primary, "self-start")),
            action=f"/events/{event_id}/import",
            method="post",
            enctype="multipart/form-data",
            cls=(FlexT.block, FlexT.column, "gap-6"),
        ),
    )


def register_routes(rt, store):
    @rt("/events/{event_id}/import", methods=["GET"])
    def import_page(event_id: int):
        return RedirectResponse(f"/events/{event_id}", status_code=303)

    @rt("/events/{event_id}/import", methods=["POST"])
    async def import_files(event_id: int, req: Request):
        form = await req.form()
        return await process_uploads(
            event_id,
            {
                "entrants": form.get("entrants_file"),
                "prizes": form.get("prizes_file"),
            },
        )

    async def process_uploads(event_id: int, uploads):
        contents = {}
        for kind, upload in uploads.items():
            if upload is None or not getattr(upload, "filename", ""):
                continue
            try:
                contents[kind] = (await upload.read()).decode("utf-8-sig")
            except UnicodeDecodeError:
                return redirect_event(event_id, "invalid-encoding")

        if not contents:
            return redirect_event(event_id, "no-file")

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
        return redirect_event(event_id, status)

    async def import_csv(event_id: int, req: Request, kind: str):
        form = await req.form()
        return await process_uploads(event_id, {kind: form.get("file")})

    @rt("/events/{event_id}/entrants/import", methods=["POST"])
    async def import_entrants(event_id: int, req: Request):
        return await import_csv(event_id, req, "entrants")

    @rt("/events/{event_id}/prizes/import", methods=["POST"])
    async def import_prizes(event_id: int, req: Request):
        return await import_csv(event_id, req, "prizes")
