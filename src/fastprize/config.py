import logging
import os
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

DEFAULT_BILLING_URL = "https://fastprize.net/billing"
DEFAULT_RESEND_FROM = "FastPrize <hello@fastprize.net>"
_LOCAL_HTTP_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_TRUE_FLAGS = frozenset({"1", "true", "yes"})


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in _TRUE_FLAGS


def resend_api_key() -> str:
    return os.environ.get("RESEND_API_KEY", "").strip()


def resend_from() -> str:
    return os.environ.get("RESEND_FROM", "").strip() or DEFAULT_RESEND_FROM


def billing_url() -> str:
    raw = os.environ.get("BILLING_URL", "").strip()
    if not raw:
        return DEFAULT_BILLING_URL
    parsed = urlsplit(raw)
    hostname = (parsed.hostname or "").casefold()
    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        return DEFAULT_BILLING_URL
    if parsed.scheme == "http" and hostname not in _LOCAL_HTTP_HOSTS:
        return DEFAULT_BILLING_URL
    return raw


def normalize_app_base_url(value: str) -> str | None:
    parsed = urlsplit(value.strip())
    hostname = (parsed.hostname or "").casefold()
    if (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or not hostname
        or not parsed.netloc
    ):
        return None
    if parsed.scheme == "https":
        return f"https://{parsed.netloc}"
    if parsed.scheme == "http" and hostname in _LOCAL_HTTP_HOSTS:
        return f"http://{parsed.netloc}"
    return None


def origin_base_url(req) -> str | None:
    origin = req.headers.get("origin", "").strip()
    if not origin:
        return None
    parsed = urlsplit(origin)
    if (
        parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
    ):
        return None
    request_host = req.headers.get("host", "")
    if parsed.scheme.casefold() != req.url.scheme.casefold():
        return None
    if parsed.netloc.casefold() != request_host.casefold():
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def resolve_public_base_url(req) -> str | None:
    raw = os.environ.get("APP_BASE_URL", "").strip()
    if raw:
        normalized = normalize_app_base_url(raw)
        if normalized:
            return normalized
        logger.warning("APP_BASE_URL is not a safe absolute URL; ignoring it")
    return origin_base_url(req)
