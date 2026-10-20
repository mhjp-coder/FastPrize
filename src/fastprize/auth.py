import hmac
import re
import secrets
from collections.abc import Mapping
from urllib.parse import urlencode, urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fasthtml.common import HTTPException, Meta, RedirectResponse

PASSWORD_HASHER = PasswordHasher()
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))
SESSION_ADMIN_ID = "admin_id"
SESSION_AUTH_VERSION = "admin_auth_version"
SESSION_CSRF_TOKEN = "csrf_token"


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Passwords must be at least 12 characters long")
    if len(password) > 1024:
        raise ValueError("Password is too long")
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def verify_unknown_password(password: str) -> None:
    verify_password(DUMMY_PASSWORD_HASH, password)


def is_safe_return_path(value: str | None) -> str:
    if not value:
        return "/"
    parsed = urlsplit(value)
    if (
        parsed.scheme
        or parsed.netloc
        or not value.startswith("/")
        or value.startswith("//")
    ):
        return "/"
    return value


def require_admin(store, req, sess):
    admin_id = sess.get(SESSION_ADMIN_ID)
    auth_version = sess.get(SESSION_AUTH_VERSION)
    admin = store.get_admin(admin_id) if isinstance(admin_id, int) else None
    if admin is None or not admin["enabled"] or auth_version != admin["auth_version"]:
        sess.pop(SESSION_ADMIN_ID, None)
        sess.pop(SESSION_AUTH_VERSION, None)
        return_path = req.url.path
        if req.url.query:
            return_path += "?" + req.url.query
        destination = "/login?" + urlencode({"next": return_path})
        return RedirectResponse(destination, status_code=303)
    return admin


def auth_beforeware(store):
    public_paths = (
        "/login",
        "/events/\\d+/display",
        "/events/\\d+/display/latest-fragment",
        "/events/\\d+/display/latest",
        "/assets/.*",
    )

    def display_slug(path: str) -> str | None:
        parts = [part for part in path.split("/") if part]
        if len(parts) == 1:
            return parts[0]
        if len(parts) == 2 and parts[1] == "latest":
            return parts[0]
        return None

    def is_public_path(path: str) -> bool:
        if any(re.fullmatch(pattern, path) for pattern in public_paths):
            return True
        slug = display_slug(path)
        return bool(slug) and store.get_event_by_slug(slug) is not None

    def same_origin(req) -> bool:
        origin = req.headers.get("origin")
        if not origin:
            return False
        parsed = urlsplit(origin)
        return (
            parsed.scheme.casefold() == req.url.scheme.casefold()
            and parsed.netloc.casefold() == req.headers.get("host", "").casefold()
        )

    async def before(req, sess):
        token = sess.get(SESSION_CSRF_TOKEN)
        if not isinstance(token, str):
            token = secrets.token_urlsafe(32)
            sess[SESSION_CSRF_TOKEN] = token
        req.hdrs.append(Meta(name="csrf-token", content=token))

        if req.method not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            supplied_token = req.headers.get("x-csrf-token", "")
            if not (
                supplied_token and hmac.compare_digest(token, supplied_token)
            ) and not same_origin(req):
                raise HTTPException(status_code=403, detail="Request rejected")

        if is_public_path(req.url.path):
            return None
        admin = require_admin(store, req, sess)
        if isinstance(admin, RedirectResponse):
            return admin
        req.state.admin = admin
        return None

    return before


def admin_from_request(req) -> dict | None:
    return getattr(req.state, "admin", None)


def csrf_token(req) -> str:
    return req.session[SESSION_CSRF_TOKEN]


def establish_session(sess, admin: Mapping) -> None:
    sess.clear()
    sess[SESSION_ADMIN_ID] = admin["id"]
    sess[SESSION_AUTH_VERSION] = admin["auth_version"]
    sess[SESSION_CSRF_TOKEN] = secrets.token_urlsafe(32)


def clear_session(sess) -> None:
    sess.clear()


def login_rate_subject(email: str) -> str:
    return email.strip().casefold()
