# pyright: reportMissingImports=false
import os
from pathlib import Path
from urllib.parse import urlsplit

from fasthtml.common import fast_app, serve
from starlette.staticfiles import StaticFiles

from fastprize.store import PrizeDrawStore
from fastprize.ui import EVENT_SELECTION_COOKIE
from fastprize.views import draw, entrants, events, history, imports, prizes

EVENT_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def _event_id_from_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "events" and parts[1].isdigit():
        return int(parts[1])
    return None


class _SelectedEventCookieMiddleware:
    def __init__(self, app, store):
        self.app = app
        self.store = store

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_cookie(message):
            if message["type"] == "http.response.start":
                event_id = _event_id_from_path(scope["path"])
                if event_id is None:
                    location = next(
                        (
                            value.decode("latin-1")
                            for name, value in message.get("headers", [])
                            if name.lower() == b"location"
                        ),
                        "",
                    )
                    event_id = _event_id_from_path(urlsplit(location).path)

                if event_id is not None and self.store.get_event(event_id) is not None:
                    cookie = (
                        f"{EVENT_SELECTION_COOKIE}={event_id}; "
                        f"Max-Age={EVENT_COOKIE_MAX_AGE}; Path=/; HttpOnly; SameSite=lax"
                    )
                    if scope["scheme"] == "https":
                        cookie += "; Secure"
                    message = {
                        **message,
                        "headers": [
                            *message.get("headers", []),
                            (b"set-cookie", cookie.encode("ascii")),
                        ],
                    }
            await send(message)

        await self.app(scope, receive, send_with_cookie)


def create_app(db_path: str | Path | None = None):
    database = db_path or os.environ.get("FASTPRIZE_DB_PATH", "fastprize.sqlite3")
    store = PrizeDrawStore(database)
    app, rt = fast_app(title="FastPrize", pico=False, surreal=False, htmx=False)
    asset_directory = Path(__file__).resolve().parents[2] / "assets"
    app.mount("/assets", StaticFiles(directory=asset_directory), name="assets")

    app.add_middleware(_SelectedEventCookieMiddleware, store=store)

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
