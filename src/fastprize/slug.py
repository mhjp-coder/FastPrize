import re
import unicodedata

RESERVED_SLUGS = {"login", "logout", "events", "admin", "assets"}
_SLUG_BREAKS = re.compile(r"[^a-z0-9]+")


def event_slug(name: str) -> str:
    ascii_name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    slug = _SLUG_BREAKS.sub("_", ascii_name.casefold()).strip("_")
    return slug or "event"


def public_event_slug(event: dict, events: list[dict]) -> str:
    base = event_slug(event["name"])
    matches = sorted(
        (item for item in events if event_slug(item["name"]) == base),
        key=lambda item: item["id"],
    )
    slug = base if matches and matches[0]["id"] == event["id"] else f"{base}_{event['id']}"
    if slug in RESERVED_SLUGS:
        slug = f"{slug}_{event['id']}"
    return slug
