import json

from fasthtml.common import (
    HTTPException,
    RedirectResponse,
    Request,
)

from fastprize.ui import redirect_event


def register_routes(rt, store):
    @rt("/events/{event_id}/import", methods=["GET", "POST"])
    async def import_page(event_id: int, req: Request):
        event = store.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404)
        if req.method == "GET":
            return RedirectResponse(f"/events/{event_id}#csv-import", status_code=303)
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
