# pyright: reportMissingImports=false
import os
from pathlib import Path
from urllib.parse import urlsplit

from fasthtml.common import Beforeware, fast_app, serve
from starlette.staticfiles import StaticFiles

from fastprize.auth import auth_beforeware, hash_password
from fastprize.store import PrizeDrawStore, get_database_path
from fastprize.ui import EVENT_SELECTION_COOKIE
from fastprize.views import auth, draw, entrants, events, history, imports, prizes

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
    database = db_path or get_database_path()
    store = PrizeDrawStore(database)
    secure_cookies = os.environ.get("FASTPRIZE_COOKIE_SECURE", "").casefold() in {
        "1",
        "true",
        "yes",
    }
    session_secret = os.environ.get("FASTPRIZE_SESSION_SECRET") or None
    if secure_cookies and (session_secret is None or len(session_secret) < 32):
        raise RuntimeError(
            "FASTPRIZE_COOKIE_SECURE requires FASTPRIZE_SESSION_SECRET with at least 32 characters"
        )
    bootstrap_email = os.environ.get("FASTPRIZE_ADMIN_EMAIL", "").strip()
    bootstrap_password = os.environ.get("FASTPRIZE_ADMIN_PASSWORD", "")
    if bool(bootstrap_email) != bool(bootstrap_password):
        raise RuntimeError(
            "Set both FASTPRIZE_ADMIN_EMAIL and FASTPRIZE_ADMIN_PASSWORD to bootstrap an admin"
        )
    if bootstrap_email and not store.admin_count():
        store.bootstrap_admin(bootstrap_email, hash_password(bootstrap_password))

    app, rt = fast_app(
        title="FastPrize",
        pico=False,
        surreal=False,
        htmx=True,
        secret_key=session_secret,
        session_cookie="fastprize_session",
        max_age=60 * 60 * 24 * 7,
        same_site="lax",
        sess_https_only=secure_cookies,
        before=Beforeware(auth_beforeware(store)),
    )

    app.add_middleware(_SelectedEventCookieMiddleware, store=store)
    app.state.store = store
    asset_directory = Path(__file__).resolve().parents[2] / "assets"
    app.mount("/assets", StaticFiles(directory=asset_directory), name="assets")

    for register_routes in (
        auth.register_routes,
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
