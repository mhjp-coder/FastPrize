# pyright: reportMissingImports=false
import os
from pathlib import Path
from urllib.parse import urlsplit

from fasthtml.common import fast_app, serve
from starlette.middleware.base import BaseHTTPMiddleware

from fastprize.store import PrizeDrawStore
from fastprize.ui import EVENT_SELECTION_COOKIE
from fastprize.views import draw, entrants, events, history, imports, prizes

EVENT_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def _event_id_from_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "events" and parts[1].isdigit():
        return int(parts[1])
    return None


def create_app(db_path: str | Path | None = None):
    database = db_path or os.environ.get("FASTPRIZE_DB_PATH", "fastprize.sqlite3")
    store = PrizeDrawStore(database)
    app, rt = fast_app(title="FastPrize", pico=False, surreal=False, htmx=False)

    async def remember_selected_event(request, call_next):
        response = await call_next(request)
        event_id = _event_id_from_path(request.url.path)
        if event_id is None:
            location = response.headers.get("location", "")
            event_id = _event_id_from_path(urlsplit(location).path)
        if event_id is not None and store.get_event(event_id) is not None:
            response.set_cookie(
                EVENT_SELECTION_COOKIE,
                str(event_id),
                max_age=EVENT_COOKIE_MAX_AGE,
                path="/",
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https",
            )
        return response

    app.add_middleware(BaseHTTPMiddleware, dispatch=remember_selected_event)

    for register_routes in (
        events.register_routes,
        imports.register_routes,
        entrants.register_routes,
        prizes.register_routes,
        draw.register_routes,
        history.register_routes,
    ):
        register_routes(rt, store)

    return app, store


app, store = create_app()


def main() -> None:
    serve()
