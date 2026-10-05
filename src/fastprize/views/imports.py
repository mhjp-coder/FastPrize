from fasthtml.common import H1, H2, Button, Div, Form, Input, Label, P, Small
from starlette.exceptions import HTTPException
from starlette.requests import Request

from fastprize.ui import document, redirect_event, status_message


def register_routes(rt, store):
    @rt("/events/{event_id}/import")
    def import_page(event_id: int, status: str = ""):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        message = status_message(status)
        return document(
            f"FastPrize | {event['name']} | Import",
            Div(
                Div("EVENT DATA", class_="eyebrow"),
                H1("Import CSV"),
                P(f"Load entrants and prizes into {event['name']}."),
                class_="page-intro",
            ),
            P(message, class_="notice") if message else "",
            Div(
                Div(
                    H2("Entrants"),
                    Small("Import names and organizations."),
                    Form(
                        Input(
                            type="file",
                            name="file",
                            accept=".csv,text/csv",
                            required=True,
                        ),
                        Button("Import entrants", type="submit", class_="secondary"),
                        action=f"/events/{event_id}/entrants/import",
                        method="post",
                        enctype="multipart/form-data",
                        class_="import-form",
                    ),
                ),
                Div(
                    H2("Prizes"),
                    Small("Import prize names and sponsors."),
                    Form(
                        Input(
                            type="file",
                            name="file",
                            accept=".csv,text/csv",
                            required=True,
                        ),
                        Button("Import prizes", type="submit", class_="secondary"),
                        action=f"/events/{event_id}/prizes/import",
                        method="post",
                        enctype="multipart/form-data",
                        class_="import-form",
                    ),
                ),
                class_="import-grid",
            ),
            event_id=event_id,
            event_name=event["name"],
            active_link="import",
        )

    async def import_csv(event_id: int, req: Request, kind: str):
        form = await req.form()
        upload = form.get("file")
        if upload is None or not getattr(upload, "filename", ""):
            return redirect_event(event_id, "no-file", "import")
        try:
            content = (await upload.read()).decode("utf-8-sig")
        except UnicodeDecodeError:
            return redirect_event(event_id, "invalid-encoding", "import")
        if kind == "entrants":
            report = store.import_entrants(event_id, content)
            status = f"entrants-imported:{report.added}:{report.duplicates}:{len(report.errors)}:{'; '.join(report.errors[:3])}"
        else:
            report = store.import_prizes(event_id, content)
            status = f"prizes-imported:{report.added}:0:{len(report.errors)}:{'; '.join(report.errors[:3])}"
        return redirect_event(event_id, status, "import")

    @rt("/events/{event_id}/entrants/import", methods=["POST"])
    async def import_entrants(event_id: int, req: Request):
        return await import_csv(event_id, req, "entrants")

    @rt("/events/{event_id}/prizes/import", methods=["POST"])
    async def import_prizes(event_id: int, req: Request):
        return await import_csv(event_id, req, "prizes")
